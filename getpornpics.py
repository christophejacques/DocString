import sys
import re
import traceback
import winsound
import ctypes
import requests
import webbrowser

from ctypes import wintypes
from selectolax.parser import HTMLParser, Node
from loguru import logger
from time import sleep
from pathlib import Path
from typing import Optional, Generator
from threading import Thread


PORNSTAR: str = "Tifa"
WEBSITE = """
https://www.pornpics.com/pornstars/
"""

QUITTER: str = """
Copier/Coller la ligne ci-dessous pour arrêter
QUIT
"""


class PressPapier:

    def __init__(self):

        # Définition des types et constantes de l'API Windows
        self.CF_UNICODETEXT = 13

        self.OpenClipboard = ctypes.windll.user32.OpenClipboard
        self.OpenClipboard.argtypes = [wintypes.HWND]
        self.OpenClipboard.restype = wintypes.BOOL

        self.CloseClipboard = ctypes.windll.user32.CloseClipboard
        self.CloseClipboard.argtypes = []
        self.CloseClipboard.restype = wintypes.BOOL

        self.GetClipboardData = ctypes.windll.user32.GetClipboardData
        self.GetClipboardData.argtypes = [wintypes.UINT]
        self.GetClipboardData.restype = wintypes.HANDLE

        self.GlobalLock = ctypes.windll.kernel32.GlobalLock
        self.GlobalLock.argtypes = [wintypes.HANDLE]
        self.GlobalLock.restype = ctypes.c_void_p

        self.GlobalUnlock = ctypes.windll.kernel32.GlobalUnlock
        self.GlobalUnlock.argtypes = [wintypes.HANDLE]
        self.GlobalUnlock.restype = wintypes.BOOL

        self.contenu: list = list()
        print("Attente de sélection d'une page html pour:", PORNSTAR, flush=True)
        self.thread = Thread(target=self.check)
        self.thread.start()

    def beep(self, freq, duree=500):
        # winsound.Beep(frequence, duree)
        winsound.Beep(freq, duree)

    def get_clipboard_windows(self) -> str:
        text = ""
        # 1. Ouvrir le presse-papiers
        if self.OpenClipboard(None):
            try:
                # 2. Récupérer le handle des données au format texte Unicode
                h_clip_mem = self.GetClipboardData(self.CF_UNICODETEXT)
                if h_clip_mem:
                    # 3. Verrouiller la mémoire pour pouvoir lire les données
                    data_ptr = self.GlobalLock(h_clip_mem)
                    if data_ptr:
                        text = str(ctypes.c_wchar_p(data_ptr).value)
                        self.GlobalUnlock(h_clip_mem)
            finally:
                # 4. Toujours refermer le presse-papiers
                self.CloseClipboard()
        return text

    def is_downloadable_url(self, url) -> bool:
        if not url.startswith("https://"):
            return False

        if len(url.split("\n")) != 1:
            return False

        url_splited = [int(text) if text.isdigit() else text.lower() 
            for text in re.split(r'(\d+)', url)]

        return (len(url_splited) > 2 and 
            url_splited[-1] == "/" and 
            type(url_splited[-2]) is int)

    def check(self):
        # boucle jusqu'au copier/coller d'un adresse
        texte_recupere = ""
        is_address = False
        while not is_address and texte_recupere.strip() != "QUIT":
            texte_recupere = self.get_clipboard_windows()
            is_address = self.is_downloadable_url(texte_recupere)
            sleep(0.2)

        if texte_recupere.strip() == "QUIT":
            return

        # Une adresse a été sélectionnée
        url = ""
        while is_address:
            is_address = False
            texte_recupere = self.get_clipboard_windows()

            if self.is_downloadable_url(texte_recupere):
                is_address = True
                if url != texte_recupere:
                    url = texte_recupere
                    self.contenu.append(url)
                    self.beep(1500)

            if is_address:
                sleep(0.2)

    def get(self) -> Generator:
        while self.thread.is_alive() or len(self.contenu) > 0:
            sleep(0.2)

            if len(self.contenu) == 0:
                continue

            if self.contenu[0] is None:
                self.close()
                return

            else:
                yield self.contenu.pop(0)

    def close(self):
        # Détruire l'instance pour libérer la mémoire
        self.contenu.clear()
        self.beep_end()

    def beep_begin(self):
        self.beep(1000)

    def beep_done(self):
        self.beep(800, 300)
        sleep(0.10)
        self.beep(800, 300)

    def beep_end(self):
        self.beep(1200)
        sleep(0.05)
        self.beep(1200)
        sleep(0.05)
        self.beep(1200)


class Main:

    def __init__(self):

        # Ouvrir la page dans Firefox
        webbrowser.open_new_tab(WEBSITE.strip())

        # logger.trace
        # logger.debug
        # logger.info
        # logger.success
        # logger.warning
        # logger.error
        # logger.critical

        # vide le fichier de log
        with open("books.log", "a"):  # w: overwrite, a: append
            pass

        # reinitialise les logs
        logger.remove()

        # Ajout des erreurs dans le fichier de log
        logger.add("books.log", level="INFO", rotation="500 KB")

        # Affichage de information a l'ecran
        logger.add(sys.stdout, level="TRACE")

        self.HEADER: dict = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:152.0) Gecko/20100101 Firefox/152.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "fr,fr-FR;q=0.9,en-US;q=0.8,en;q=0.7",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-User": "?1",
            "Priority": "u=0, i",
            "Referer": "https://www.pornpics.com/pornstars/"
        }

        pp = PressPapier()

        # creation de la session pour tous les acces au site
        self.session: requests.Session = requests.Session()
        self.total_dirs: int = 0
        self.total_files: int = 0

        for url in pp.get():
            pp.beep_begin()
            no_error = self.scrap(url)
            pp.beep_done()

            if no_error:
                sleep(0.2)
            else:
                break
        
        pp.close()

        msg = "Téléchargement total: "
        msg += f"{self.total_dirs} répertoire" + ("s" if self.total_dirs > 1 else "")
        msg += f", {self.total_files} image" + ("s" if self.total_files > 1 else "")
        logger.success(msg)

    def title2directory(self, title: str) -> str:

        # title = title[:6]
        recherche = title
        for aSuppr in re.findall(r"\[[^]]*\]", recherche):
            title = title.replace(aSuppr, "")
        title = title.replace("/", " ").replace(">", " ").replace("<", " ")
        return title.replace("|", "-").replace(":", "-").replace("  ", " ").strip().title()

    def download(self, directory: Path, nom_fichier: str, url: Optional[str]):

        if url is None:
            return

        try:
            response = self.session.get(url)
            response.raise_for_status()

        except Exception as erreur:
            logger.critical("ERREUR:", erreur)
            raise

        type_fichier, extension = response.headers.get("Content-Type", "").split("/")
        if type_fichier != "image":
            logger.success(f"Not an image: {url}")
            return

        logger.success(f"Downloading {nom_fichier}")
        with open(directory / nom_fichier, "wb") as fh_img:
            fh_img.write(response.content)

    def scrap(self, next_url: Optional[str]) -> Optional[bool]:
        resultat: Node 

        url: str = ""
        current: int = 1
        total: int = 0

        file_already_downloaded: bool = False

        msg = f"Scraping {next_url}"
        logger.success(msg)

        while next_url != url and not file_already_downloaded:

            if next_url is None:
                url = ""
            else:
                url = next_url

            retry = 3
            while retry > 0:
                try:
                    response = self.session.get(url, timeout=5, 
                        headers=self.HEADER)
                    response.raise_for_status()

                except Exception as erreur:
                    logger.critical(f"Erreur: {erreur}")

                    # return Error = True
                    return True

                tree = HTMLParser(response.text)
                titlecss = tree.css_first(".title-section > h1:nth-child(1)")
                if titlecss is None:
                    logger.critical("Erreur de récupération du Titre")
                    retry = 0
                    continue

                title = self.title2directory(titlecss.text())

                directory = Path("pornpics") / PORNSTAR / title

                if not directory.exists():
                    directory.mkdir(parents=True)
                    logger.success(f"répertoire créé: {directory}")
                    self.total_dirs += 1

                resultat = tree.css_first("#tiles")
                if resultat is None:
                    logger.critical("Erreur de récupération de #tiles")
                    retry = 0
                    continue

                child = resultat.css_first(f"li.thumbwook:nth-child({current}) > a")
                if child:
                    urlattr = child.attributes.get("href", "")
                    url = str(urlattr)
                    nom_fichier = url.split("/")[-1]

                    if (directory / nom_fichier).exists():
                        logger.info(f"le fichier: {nom_fichier} existe déjà")
                        file_already_downloaded = True
                        
                    else:
                        try:
                            self.download(directory, nom_fichier, url)

                        except Exception as erreur:
                            logger.error(f"Download Error ({retry}): {erreur}")
                            retry -= 1
                            continue

                        current += 1
                        self.total_files += 1

                total = current - 1
                retry = -10

        logger.success(f"{total} images téléchargées")

        return retry != 0


if __name__ == '__main__':
    try:
        Main()

    except Exception:
        logger.critical(traceback.format_exc())
