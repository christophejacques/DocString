import sys
import re
import traceback

import requests
from selectolax.parser import HTMLParser, Node
from loguru import logger
from time import sleep
from pathlib import Path
from typing import Optional


# logger.trace
# logger.debug
# logger.info
# logger.success
# logger.warning
# logger.error
# logger.critical

SAVE_FILENAME: str = "_lastURL.cfg"

# 
last_directory: str = ""
url = """
https://e-hentai.org/s/8e5b222ff1/3936893-1256
"""


def get_last_url() -> Optional[str]:
    if not Path(SAVE_FILENAME).exists():
        return None

    with open(SAVE_FILENAME) as fhandle:
        url = fhandle.read()

    return url.strip()


def save_last_url(url: str):
    with open(SAVE_FILENAME, "w") as fhandle:
        fhandle.write(f"{url}".strip())


last_url = get_last_url()
if last_url is not None:
    url = last_url


BASE_URL: str = url.strip()
MAX_TEL: int = 2000


def get_referer(url: str) -> str:
    *liste_referer, nombre = url.split("-")
    referer = "-".join(liste_referer)
    if nombre.isdigit():
        if nombre == "1":
            referer += "-" + str(int(nombre)+1)
        else:
            referer += "-" + str(int(nombre)-1)

    return referer


# vide le fichier de log
with open("books.log", "a"):  # w: overwrite, a: append
    pass

# reinitialise les logs
logger.remove()

# Ajout des erreurs dans le fichier de log
logger.add("books.log", level="INFO", rotation="500 KB")

# Affichage de information a l'ecran
logger.add(sys.stdout, level="TRACE")

HEADER: dict = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Accept-Language": "fr,fr-FR;q=0.9,en-US;q=0.8,en;q=0.7",
    "Connection": "keep-alive",
    "Host": "e-hentai.org",
    "Priority": "u=0, i",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-User": "?1",
    "TE": "trailers",
    "Upgrade-Insecure-Requests": "1",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:150.0) Gecko/20100101 Firefox/150.0",
}


def title2directory(title: str) -> str:

    # title = title[:6]
    recherche = title
    for aSuppr in re.findall(r"\[[^]]*\]", recherche):
        title = title.replace(aSuppr, "")
    title = title.replace("/", " ").replace(">", " ").replace("<", " ")
    return title.replace("|", "-").replace(":", "-").replace("  ", " ").strip().title()


def download(session: requests.Session, directory: str, nom_fichier: str, url: Optional[str]):

    if url is None:
        return

    response = session.get(url)
    response.raise_for_status()

    type_fichier, extension = response.headers.get("Content-Type", "").split("/")
    if type_fichier != "image":
        logger.success(f"Not an image: {url}")
        return

    nom_fichier = f"{nom_fichier}.{extension}"

    # logger.success(f"Downloading {nom_fichier} from: {url}")
    with open(Path(directory) / nom_fichier, "wb") as fh_img:
        fh_img.write(response.content)


def main() -> None:
    # creation de la session pour tous les acces au site
    session: requests.Session = requests.Session()
    session.headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0"

    directory: Path = Path(".")
    last_directory: str = ""
    nom_fichier: str = ""
    next_url: str = BASE_URL
    url: str = ""
    nombre: int = 0

    while next_url != url:
        url = next_url

        # HEADER.update({"Referer": get_referer(url)})
        retry = 3
        while retry > 0:
            response = session.get(url, timeout=5, headers=HEADER)
            try:
                response.raise_for_status()
            except Exception as erreur:
                logger.error(f"Erreur: {erreur}")
                return

            logger.success(f"Scraping {url}")

            tree = HTMLParser(response.text)
            resultat: Node = tree.css_first("img#img")
            if not resultat or resultat is None:
                retry -= 1
                if retry == 0:
                    save_last_url(url)
                    logger.info(f"URL de recherche Sauvegardé: {url}")

                elif retry > 0:
                    msg = "Aucune image '#img' dans la page d'index"
                    msg += f", Reste {retry} retry."
                    logger.error(msg)
                    sleep(5)

            else:
                retry = -10

        if retry == 0:
            break

        # Suppression du fichier de sauvegarde s'il existe
        if Path(SAVE_FILENAME).exists():
            Path(SAVE_FILENAME).unlink()
            logger.info("Fichier de sauvegarde de l'url de recherche supprimé")

        title = tree.css_first("title")
        if not title:
            logger.error("Aucun titre trouve sur la page")
            break

        directory = Path("img") / title2directory(title.text())
        if not directory.exists():
            rep = f"{directory}".encode().decode()
            last_directory = rep
            logger.success(f"Creation repertoire: {rep}")
            directory.mkdir()

        nom_fichier = url.split('/')[-1]

        # Rechercher toutes les extensions pour "mon_fichier"
        fichiers_trouves = list(directory.glob(f"{nom_fichier}.*"))
        if len(fichiers_trouves) > 0:
            # un fichier a été trouvé
            for fichier in fichiers_trouves:
                logger.info(f"Fichier déjà téléchargé: {fichier.name}")
                break

        else:
            download(session, str(directory), nom_fichier, resultat.attributes['src'])
            nombre += 1

        if nombre < MAX_TEL:
            sleep(0.3)

            if resultat.parent:
                next_url = resultat.parent.attributes['href']

    if not last_directory:
        last_directory = f"{directory}".encode().decode()
    logger.info(f"Repertoire utilise: {last_directory}")


if __name__ == '__main__':
    try:
        main()

    except Exception:
        logger.critical(traceback.format_exc())
