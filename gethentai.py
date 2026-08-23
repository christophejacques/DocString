import sys
import re
import traceback

import requests
from selectolax.parser import HTMLParser, Node
from loguru import logger
from time import sleep
from pathlib import Path
from typing import Optional, Generator


# logger.trace
# logger.debug
# logger.info
# logger.success
# logger.warning
# logger.error
# logger.critical

SAVE_FILENAME: str = "_lastURL.cfg"
BASE_URL: Optional[str]
GEN_URL: Generator

# 
last_directory: str = ""
urls = """
https://e-hentai.org/s/d4c9108c09/4116420-1

"""


def get_url(urls):
    for url in urls.strip().split("\n"):
        yield url.strip()


GEN_URL = get_url(urls)


def gen_next_url():
    return next(GEN_URL)


def get_last_url() -> Optional[str]:
    if not Path(SAVE_FILENAME).exists():
        return None

    with open(SAVE_FILENAME) as fhandle:
        url = fhandle.read()

    url = url.strip()
    logger.info(f"URL de recherche chargé: {url}")
    return url


def save_last_url(url: str):
    with open(SAVE_FILENAME, "w") as fhandle:
        fhandle.write(f"{url}".strip())

    logger.info(f"URL de recherche Sauvegardé: {url}")


last_url = get_last_url()
if last_url is None:
    BASE_URL = gen_next_url()
else:
    BASE_URL = last_url


MAX_TEL: int = 2000


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


def download(session: requests.Session, 
        directory: str, nom_fichier: str, url: Optional[str]):

    if url is None:
        return

    try:
        response = session.get(url)
        response.raise_for_status()
    except Exception as erreur:
        logger.critical("ERREUR:", erreur)
        raise

    type_fichier, extension = response.headers.get("Content-Type", "").split("/")
    if type_fichier != "image":
        logger.success(f"Not an image: {url}")
        return

    nom_fichier = f"{nom_fichier}.{extension}"

    # logger.success(f"Downloading {nom_fichier} from: {url}")
    with open(Path(directory) / nom_fichier, "wb") as fh_img:
        fh_img.write(response.content)


def main() -> Optional[bool]:
    resultat: Node 

    # creation de la session pour tous les acces au site
    session: requests.Session = requests.Session()
    session.headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0"

    directory: Path = Path(".")
    last_directory: str = ""
    nom_fichier: str = ""
    next_url: Optional[str] = BASE_URL
    url: str = ""
    nombre: int = 0
    current: str = ""
    total: str = ""

    file_already_downloaded: bool = False

    while next_url != url and not file_already_downloaded:

        if next_url is None:
            url = ""
        else:
            url = next_url

        retry = 3
        while retry > 0:
            try:
                response = session.get(url, timeout=5, headers=HEADER)
                response.raise_for_status()
            except Exception as erreur:
                logger.error(f"Erreur: {erreur}")
                # return Error = True
                return True

            msg = f"Scraping {url}"
            if total != "" and current.isdigit():
                msg += f" ({1+int(current)} / {total})"

            logger.success(msg)

            tree = HTMLParser(response.text)
            resultat = tree.css_first("img#img")
            if not resultat or resultat is None:
                retry -= 1
                if retry == 0:
                    save_last_url(url)
                    
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

        current_number: Node = tree.css_first("div.sn:nth-child(1) > div:nth-child(3) > span:nth-child(1)")
        if current_number is not None:
            nombre_total: Node = tree.css_first("div.sn:nth-child(1) > div:nth-child(3) > span:nth-child(2)")
            if nombre_total is not None:
                current = current_number.text()
                total = nombre_total.text()
        else:
            total = ""

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
                file_already_downloaded = True
                break

        else:
            try:
                download(session, str(directory), nom_fichier, resultat.attributes['src'])
                nombre += 1
            except Exception:
                logger.error("Erreur de téléchargement")
                save_last_url(url)
                nombre = MAX_TEL
                retry = 0

        if nombre < MAX_TEL:
            sleep(0.3)

            if resultat.parent:
                temp_ref = resultat.parent.attributes['href']
                if temp_ref is not None:
                    next_url = temp_ref

    if not last_directory:
        last_directory = f"{directory}".encode().decode()
    logger.info(f"Repertoire utilise: {last_directory}")

    # return Error = False
    return retry == 0


if __name__ == '__main__':
    try:
        while BASE_URL:
            if main():
                break

            try:
                BASE_URL = gen_next_url()
            except StopIteration:
                BASE_URL = None

    except Exception:
        logger.critical(traceback.format_exc())
