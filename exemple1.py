import sys
import re
import traceback

import requests
from selectolax.parser import HTMLParser
from loguru import logger
from urllib.parse import urljoin

"""
Basé sur la vidéo Youtube
    Docstring
    Scraping avec Python : Formation Complète 2024
    https://www.youtube.com/watch?v=sOAZpHDEdkg&t=23064s
"""

BASE_URL: str = "https://books.toscrape.com/index.html"

# vide le fichier de log
with open("books.log", "w"):
    pass

# reinitialise les logs
logger.remove()

# Ajout des erreurs dans le fichier de log
logger.add(
    "books.log",
    level="INFO",
    rotation="500 KB")

# Affichage de information a l'ecran
logger.add(
    sys.stdout,  # sys.stderr
    level="TRACE")

# logger.trace("Trace")
# logger.debug("Debug")
# logger.info("Info")
# logger.success("Succes")
# logger.warning("Warning")
# logger.error("Erreur")
# logger.critical("Critical")


def extract_price_from_page(tree: HTMLParser) -> float:
    """
    Recherche le prix du livre afin de le retourner

    param: tree, arbre de la page chargee
    return: prix du livre (float)
    """
    price: float = 0
    try:
        resultat: str = tree.css_first("p.price_color").text().strip()
        res_search = re.search(r"\d+(\.\d+)?", resultat)
        if res_search is None:
            return 0
            
        price_string: str = res_search.group()
        price = float(price_string)

    except Exception as error:
        logger.error(f"Erreur de recuperation du prix: {error}")

    return price


def extract_quantity_from_page(tree: HTMLParser) -> float:
    """
    Recherche le nombre de livres disponibles

    param: tree, arbre de la page chargee
    return: nombre de livres (int)
    """
    quantity: float = 0

    web_element = tree.css_first("p.instock.availability")
    if web_element is None:
        logger.error("Aucune quantitee recuperable")
        return 0

    chaine_quantity: str = web_element.text().strip()
    search_result = re.search(r"\((\d+) (\w+)\)", chaine_quantity)
    if search_result is None:
        logger.error("Recuperation de la quantitee impossible")
        return 0

    resultats = search_result.groups()
    if len(resultats) != 2 or resultats[1] != "available":
        logger.error("Recuperation de la quantitee impossible")
        return 0

    try:
        quantity = float(resultats[0])

    except Exception as error:
        logger.error(f"Erreur de recuperation de la quantitee: {error}")

    return quantity


def get_book_price_from_url(session: requests.Session, url: str) -> float:
    """
    retourne le prix du livre : quantite x prix unitaire

    param: session: requete a faire dans le navigateur
    param: url de la page contenant les informations du livre

    return: nombre de livre x prix du livre
    """
    price: float
    logger.success(f"Traitement: {url.split('/')[-2]}")

    try:
        response = session.get(url)
        response.raise_for_status()

    except Exception as error:
        logger.error(f"Erreur de chargement: {url}\n{error}")
        price = 0

    else:
        content = response.headers.get("Content-Type", "")
        if "text/html" in content:
            tree = HTMLParser(response.text)
            price_unitaire = extract_price_from_page(tree)
            quantity = extract_quantity_from_page(tree)
            price = price_unitaire * quantity
            logger.info(f"Prix = Qte ({quantity:.0f}) * PU ({price_unitaire}) = {price:.2f}")

    return price


def get_next_page_url(session: requests.Session, url: str, tree: HTMLParser) -> HTMLParser:
    """
    retourne la page contenant les livre suivants

    param: session: requete a faire dans le navigateur
    param: url de la page contenant les informations du livre

    return: objet contenant la page suivante html
    """

    next_page = tree.css_first("div > ul.pager > li.next > a")
    if next_page is None:
        return None

    try:
        next_url: str = next_page.attributes["href"]

    except Exception as error:
        logger.error(f"URL de la page suivante non trouvee: \n{error}")
        return None

    logger.success(f"Chargement de la page: {next_url}")
    next_url = urljoin(url, next_url)
    try:
        response = session.get(next_url)
        response.raise_for_status()

        tree = HTMLParser(response.text)

    except Exception as error:
        logger.error(f"Erreur de chargement: {next_url}\n{error}")
        return None

    return tree


def get_all_books_price(session: requests.Session, url: str) -> tuple[float, int]:
    """
    retourne le prix de tous les livres et leur nombre
    de la page passe en parametre (url)

    param: session: requete a faire dans le navigateur
    param: url de la page contenant les informations d'un livre

    return: tuple contenant  le prix de tous les livres et leur nombre
    """

    total_price: float = 0
    books_number: int = 0

    try:
        response = session.get(url)
        response.raise_for_status()
        logger.success(f"Scraping {url}")

    except Exception as error:
        logger.error(f"Erreur de chargement: {url}\n{error}")

    else:
        tree = HTMLParser(response.text)
        while tree is not None:
            books_article = tree.css("article.product_pod > div > a")

            for book_article in books_article:
                books_number += 1
                book_url = book_article.attributes['href']
                price = get_book_price_from_url(session, urljoin(url, book_url))
                total_price += price

            tree = get_next_page_url(session, url, tree)

    return total_price, books_number


def get_all_types_books_urls(session: requests.Session, url: str) -> list[str]:
    """
    retourne une liste de tous les categories de livres

    param: session: requete a faire dans le navigateur
    param: url de la page contenant la liste des categories de livres

    return: liste de toutes les categories de livres
    """

    liste_urls: list[str] = []

    try:
        response = session.get(url)
        response.raise_for_status()
        logger.success(f"Scraping {url}")

    except Exception as error:
        logger.error(f"Erreur de chargement: {url}\n{error}")
        return []

    tree = HTMLParser(response.text)

    resultats = tree.css("div.side_categories > ul.nav.nav-list > li > ul a")
    for resultat in resultats:
        liste_urls.append(resultat.attributes["href"])

    return liste_urls[:1]


def main() -> None:
    # creation de la session pour tous les acces au site
    session: requests.Session = requests.Session()

    books_price: float
    books_number: int

    total_price: float = 0
    total_books: int = 0
    
    # Chargement de la liste des categories de livres
    books_urls: list[str] = get_all_types_books_urls(session, BASE_URL)

    # boucle sur les categories de livres
    for book_url in books_urls:
        page: str = book_url.split("/")[-2]

        # recuperation du nombre de livres et de leurs prix total d'une categorie
        books_price, books_number = get_all_books_price(session, urljoin(BASE_URL, book_url))
        total_price += books_price
        total_books += books_number
        logger.success(f"Prix de la page {page!r} = {books_price:_.2f} pour {books_number} livres")

    logger.success(f"Prix Total du site = {total_price:_.2f} pour {total_books} livres")


if __name__ == '__main__':
    try:
        main()

    except Exception:
        logger.critical(traceback.format_exc())
