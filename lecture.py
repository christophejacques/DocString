import sqlite3
import pygame
import re

from pathlib import Path
from typing import Optional, Tuple, Callable
from collections import namedtuple
from threading import Thread
from os import chdir


def fprint(*args, **kwargs):
    kwargs.pop("flush", 0)
    print(*args, **kwargs, flush=True)


class Variable: 
    DATABASE_NAME: str = "pictures.db"

    # DIRECTORY: str = r"E:\Jeux\World of Warcraft\_retail_\Screenshots"
    # SUB_DIRECTORY: str = "."

    DIRECTORY: str = r""
    SUB_DIRECTORY: str = "img"

    # DIRECTORY: str = r"F:\Images\Hentai"
    # SUB_DIRECTORY: str = "."

    SYS_FONT16: pygame.font.Font
    SYS_FONT18: pygame.font.Font
    SYS_FONT20: pygame.font.Font
    SYS_FONT22: pygame.font.Font
    SYS_FONT24: pygame.font.Font


if Variable.DIRECTORY:
    chdir(Variable.DIRECTORY)


class Factory:
    @classmethod
    def namedtuple(cls, cursor, row):
        fields = [column[0] for column in cursor.description]
        classe = namedtuple("Row", fields)
        return classe._make(row)

    @classmethod
    def dictionary(cls, cursor, row):
        fields = [column[0] for column in cursor.description]
        return {key: value for key, value in zip(fields, row)}


# Fonction pour diviser le texte en morceaux de chaînes et de nombres
def natural_sort_key(s):
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', s)]


class MySQL:

    def __init__(self, dbname: str):
        # dbname = ":memory:"
        self.cx = sqlite3.connect(dbname)
        self.cx.row_factory = Factory.namedtuple
        self.cu = self.cx.cursor()

        # reconstruction du fichier de bdd
        self.cu.execute("VACUUM")

    def close(self):
        self.cx.commit()
        self.cx.close()

    def count_table(self, 
      tablename: str, 
      distinct: Optional[str] = None, 
      where: Optional[str] = None, 
      group_by: Optional[str] = None,
      data: dict = dict()) -> int:

        if distinct:
            sql = f"SELECT count(distinct {distinct}) as nombre FROM " + tablename
        else:
            sql = "SELECT count(1) as nombre FROM " + tablename

        if where is not None:
            sql += " WHERE " + where

        if group_by is not None:
            sql += " GROUP BY " + group_by

        requete = self.cu.execute(sql, data)
        result = requete.fetchone()
        
        return result.nombre
        # return result[0]

    def delete_table(self, 
      tablename: str, 
      where: Optional[str] = None, 
      data: dict = dict()):

        sql = f"DELETE FROM {tablename}" 
        if where is not None:
            sql += " WHERE " + where

        self.cu.execute(sql, data)
        self.cx.commit()

    def create_table(self, drop_if_exists: bool = False):

        if drop_if_exists:
            self.cu.execute("DROP TABLE IF EXISTS repertoires")

        self.cu.execute("""CREATE TABLE IF NOT EXISTS repertoires(
            emplacementid integer PRIMARY KEY AUTOINCREMENT,
            emplacement text,
            pictureid integer 
        )""")

        if drop_if_exists:
            self.cu.execute("DROP TABLE IF EXISTS pictures")

        self.cu.execute("""CREATE TABLE IF NOT EXISTS pictures(
            ident integer PRIMARY KEY AUTOINCREMENT,
            emplacementid integer,
            nom text
        )""")

    def file_exists(self, emplacementid: int, nom: str, cursor) -> bool:

        sql = """
            SELECT nom 
            FROM pictures 
            WHERE nom = :nom
                AND emplacementid = :emplacementid
            """

        requete = cursor.execute(sql, {
            "emplacementid": emplacementid,
            "nom": nom
            })
        result = requete.fetchone()

        if result is None:
            return False

        return len(result) > 0

    def add_file(self):

        def walk_key_sort(e): 
            return e[0]

        # Fonction pour diviser le texte en morceaux de chaînes et de nombres
        def natural_sort_key(s):
            if s is None: 
                return []
            return [int(text) if text.isdigit() else text.lower() 
                for text in re.split(r'(\d+)', s)]

        fprint("Updating Database:", end=" ... ")
        nombre: int = 0
        rep_init = Path(Variable.SUB_DIRECTORY)
        extensions = ("jpg", "bmp", "webp", "gif", "jpeg", "png", "tiff")

        myBd = sqlite3.connect(Variable.DATABASE_NAME)
        myCursor = myBd.cursor()
        need_commit: bool = False
        repertoire_cree: bool = False
        emplacementid: int = 0

        for windowsDirectory, _, fichiers in sorted(rep_init.walk(), key=walk_key_sort):
            
            root = f"{windowsDirectory}"
            files = sorted(list(
                filter(
                    lambda x: x.split(".")[-1].lower() in extensions, fichiers)),
                key=natural_sort_key)

            nombre = len(files)
            repertoire_cree = False

            # detection de presence du repertoire
            myCursor.execute("""
                SELECT emplacementid
                FROM repertoires
                WHERE emplacement = :emplacement
                """,
                {"emplacement": root})

            result = myCursor.fetchone()
            if result is None:
                # le repertoire n'existe pas, donc on le cree
                need_commit = True
                repertoire_cree = True
                resultat = myCursor.execute("""
                    INSERT INTO repertoires (emplacement)
                    VALUES (:emplacement)
                    """, 
                    {"emplacement": root})

                emplacementid = resultat.lastrowid
                fprint("\n- Répertoire enregistré", f"(id:{emplacementid}) :", root, end="")

            else:
                # Le repertoire existe deja
                emplacementid = result[0]

            if repertoire_cree:
                liste = (0,)

            else:
                # Détection du nombre de fichier(s) manquant(s)
                placeholders = ", ".join(["?"] * nombre)
                myCursor.execute("""
                    SELECT count(1)
                    FROM pictures  
                    WHERE emplacementid = ?
                      AND nom in (""" + placeholders + ")", 
                    (emplacementid, *files))

                liste = myCursor.fetchone()

            if repertoire_cree or liste[0] != nombre:
                need_commit = True
                fprint("\nChecking:", root)
                fprint("-", len(files), end=" fichier(s) dont ")
                fprint(nombre - liste[0], "fichier(s) manquant(s)")

                #  Suppression de toutes les image(s) du répertoire
                resultat = myCursor.execute("""
                    DELETE FROM pictures  
                    WHERE emplacementid = :emplacementid
                    """, 
                    {"emplacementid": emplacementid})

                fprint("-", f"{resultat.rowcount} images supprimées")

                # Ajout de toutes les images
                liste_images = [
                    {"emplacementid": emplacementid, "nom": img} for img in files]
                resultat = myCursor.executemany("""
                    INSERT INTO pictures (emplacementid, nom)
                    VALUES (:emplacementid, :nom)
                    """, 
                    liste_images)

                fprint("-", f"{resultat.rowcount} images ajoutées", end="")

        if need_commit:
            fprint("\n+", "commit()", end=" ... ")
            myBd.commit()

        fprint("done")
        myBd.close()

    def insert_or_update(self, table: str, insert_data: dict, update_data: dict,
            where_data: dict = dict()):

        where = ','.join(map(lambda champ: f"{champ} = :{champ}", where_data.keys()))

        result = self.count_table(table, where=where, data=where_data)
        # fprint("count", table, ":", result)

        if result == 0:
            self.insert(table, insert_data)
        else:
            self.update(table, update_data=update_data, where_data=where_data)

    def update(self, table: str, update_data: dict, where_data: dict = dict()):
    
        sql = f"UPDATE {table} "
        sql += "SET "
        sql += ','.join(map(lambda champ: f"{champ} = :{champ}", update_data.keys()))

        if where_data:
            sql += " WHERE "
            sql += ','.join(map(lambda champ: f"{champ} = :{champ}", where_data.keys()))

        datas = update_data.copy()
        datas.update(where_data)
        # fprint(sql, datas)

        result = self.cu.execute(sql, datas)
        self.cx.commit()

    def insert(self, table: str, datas: dict):

        liste_valeurs = datas.keys()
        
        sql = f"INSERT INTO {table} "
        sql += f" ({','.join(liste_valeurs)}) "
        sql += "VALUES ("
        sql += ','.join(map(lambda champ: f":{champ}", liste_valeurs))
        sql += ")"

        # fprint(sql)
        result = self.cu.execute(sql, datas)

        # fprint("Resultat insert:", result)
        self.cx.commit()

    def read_files(self):
        sql = "SELECT ident, nom FROM pictures"
        requete = self.cu.execute(sql)

        result = requete.fetchall()
        for ident, fichier in enumerate(result):
            numero, nom = fichier
            print(f"{numero:5} {nom[:28]:28}", end="-")
            if ident % 4 == 3:
                print(flush=True)

        print(flush=True)

    def select_one(self, sql: str, datas: dict):

        self.cu.execute(sql, datas)
        row = self.cu.fetchone()

        return row

    def select_all(self, sql: str, datas: dict):

        self.cu.execute(sql, datas)
        rows = self.cu.fetchall()

        return rows

    def select_img(self, ident=None, nom=None) -> Optional[Tuple]:
        # 2. Récupération des informations de l'image
        myBd = sqlite3.connect(Variable.DATABASE_NAME)
        myBd.row_factory = Factory.namedtuple
        myCursor = myBd.cursor()
        
        if ident is not None:
            myCursor.execute("""
                SELECT rep.emplacementid, emplacement, nom
                FROM pictures pic
                INNER JOIN repertoires rep ON pic.emplacementid = rep.emplacementid
                WHERE ident = :ident""", 
                {"ident": ident})

        elif nom is not None:
            myCursor.execute("""
                SELECT emplacement, nom
                FROM pictures 
                WHERE nom like :nom""", 
                {"nom": f"{nom}%"})

        row = myCursor.fetchone()
        emplacement = row.emplacement
        emplacementid = row.emplacementid
        nom = row.nom

        myBd.close()

        if row is None:
            return None

        return (emplacementid, emplacement, nom)


def get_pygame_const_name(ident):
    for c in dir(pygame):
        if callable(c):
            continue

        if c[0] in "AZERTYUIOPMLKJHGFDSQWXCVBN":
            if type(getattr(pygame, c)) is int and getattr(pygame, c) == ident:
                return c

    return ident


class Commande:
    SCREEN: pygame.Surface

    name: str
    color: Tuple[int, int, int]
    coords: pygame.Rect
    callback: Optional[Callable]

    def __init__(self):
        self.screen = Commande.SCREEN
        self.mouse_clicking = False
        self.mouse_over = False

        self.set_visible(True)

    def set_visible(self, visible: bool):
        self.hidden = not visible

    def set_color(self, color: Tuple[int, int, int]):
        self.color = color

    def set_pos(self, posx: int, posy: int):
        self.coords = pygame.Rect((posx, posy, *self.coords[2:]))

    def move(self, dx: int = 0, dy: int = 0):
        self.coords.move_ip(dx, dy)

    def mouse_move(self, position: tuple):
        if self.hidden:
            self.mouse_over = False
            return

        self.mouse_over = self.coords.collidepoint(position)

    def mouse_click(self):
        if self.callback:
            self.callback()

    def mouse_down(self):
        if self.hidden:
            return

        self.mouse_clicking = self.mouse_over

    def mouse_up(self):
        if self.hidden:
            return

        if self.mouse_clicking and self.mouse_over:
            self.mouse_clicking = False
            self.mouse_click()

        else:
            self.mouse_clicking = False

    def update(self): ...


class Box(Commande):

    def __init__(self, 
    name: str, 
    color: Tuple[int, int, int], 
    coords: Tuple[int, int, int, int], 
    *args, **kwargs):
        # fprint(f"Box.__init__({name})")
        super().__init__()

        self.name = name
        self.color = color
        self.set_over_color(kwargs.get("over_color", (0, 200, 0)))

        self.coords = pygame.Rect(coords)
        self.args = args
        self.callback_ended()

        self.callback = kwargs.get("callback")
        self.params = kwargs.get("params", ())
        self.thread = kwargs.get("thread", False)

        self.lib_surf = Variable.SYS_FONT24.render(f"{self.name}", False, (200, 200, 0))

    def set_over_color(self, color: Tuple[int, int, int]):
        self.over_color = color

    def set_exec_color(self, color: Tuple[int, int, int]):
        self.exec_color = color

    def mouse_click(self):
        # fprint(f"Box {self.name!r} Clicked")
        if self.callback and not self.executing_callback:
            self.executing_callback = self.thread
            self.callback(*self.params)
            if self.thread:
                return
            self.callback_ended()

    def callback_ended(self):
        self.executing_callback = False
        self.set_exec_color((0, self.color[1], 0))

    def draw(self):
        if self.executing_callback:
            pygame.draw.rect(self.screen, self.exec_color, self.coords)

        elif self.mouse_over:
            if self.mouse_clicking:
                pygame.draw.rect(self.screen, (200, 200, 200), self.coords)
            else:
                pygame.draw.rect(self.screen, self.over_color, self.coords)
        else:
            pygame.draw.rect(self.screen, self.color, self.coords)

        if self.mouse_over:
            self.screen.blit(self.lib_surf, (200, 10))


class Image(Commande):

    nom_surf2: Optional[pygame.Surface]

    def __init__(self, 
    ident: int, 
    nom: str,
    color: Tuple[int, int, int], 
    coords: Tuple[int, int, int, int], 
    *args, **kwargs):
        # fprint(f"Image.__init__({ident}, {nom})")
        super().__init__()

        self.image_surface = None
        self.ident = ident
        self.nom = nom
        self.color = color

        epaisseur: int = 4
        self.coords = pygame.Rect(coords)
        self.coords_img = pygame.Rect(
            (coords[0]+epaisseur, coords[1]+epaisseur + 15, 
                coords[2]-2*epaisseur, coords[3]-2*epaisseur - 15))

        self.callback = kwargs.get("callback")
        self.params = kwargs.get("params", ())
        self.surface = kwargs.get("surface")
        self.nombre = kwargs.get("nombre", 0)
        self.directory = kwargs.get("emplacement", "")
        self.emplacementid = kwargs.get("emplacementid", 0)

        self.nom_surf1 = Variable.SYS_FONT16.render(f"{self.nom[:19]}", False, (200, 200, 200))
        self.coords_nom1 = (coords[0]+1, coords[1]+1)

        if len(nom) > 18:
            self.nom_surf2 = Variable.SYS_FONT16.render(f"{self.nom[19:]}", False, (200, 200, 200))
            self.coords_nom2 = (coords[0]+1, coords[1]+21)
            taille = (coords[2], 40)
        else:
            self.nom_surf2 = None
            taille = (coords[2], 20)

        self.header_position = coords[:2]
        self.footer_position = (coords[0], coords[1]+coords[3]-20-epaisseur)

        self.header = pygame.Surface(taille, pygame.SRCALPHA)
        self.footer = pygame.Surface((coords[2], 20+epaisseur), pygame.SRCALPHA)

        self.header.fill((10, 10, 10, 128))
        self.footer.fill((10, 10, 10, 192))

        self.nb_surf = Variable.SYS_FONT20.render(f"{self.nombre}", False, (200, 200, 0))

        self.header.blit(self.nom_surf1, (epaisseur, 1))
        self.footer.blit(self.nb_surf, (epaisseur, 1))
        
        self.dir_surf = Variable.SYS_FONT24.render(f"{self.directory}", False, (200, 200, 0))

        # Chargement de l'image en temps reel
        # self.init_thread(ident, self.coords_img[2:])

        # Chargement de l'image en tache de fond
        self.chargement = Thread(target=self.init_thread, args=(ident, self.coords_img[2:]))
        self.chargement.start()

    def init_thread(self, ident: int, size: list[int]):
        if self.surface:
            self.image_surface, decalx, decaly = self.surface(ident, size)
            self.coords_img[0] += decalx
            self.coords_img[1] += decaly

    def mouse_click(self):
        # fprint(f"Image {self.nom!r} Clicked")
        if self.callback:
            # self.callback(*self.params, self.nom)
            self.callback(*self.params, self.emplacementid)

    def draw(self):
        if self.mouse_over:
            pygame.draw.rect(self.screen, 
                (self.color[0], 100, self.color[2]), self.coords)
        else:
            pygame.draw.rect(self.screen, self.color, self.coords)

        self.screen.blit(self.header, self.header_position)

        if self.image_surface:
            self.screen.blit(self.image_surface, self.coords_img[:2])

            if self.nom_surf2:
                self.screen.blit(self.nom_surf2, self.coords_nom2)

            if self.mouse_over:
                self.screen.blit(self.dir_surf, (200, 10))

        self.screen.blit(self.footer, self.footer_position)


class Fleche(Commande):

    def __init__(self, 
    name: str, 
    color: Tuple[int, int, int], 
    coords: Tuple[int, int, int, int], 
    *args, **kwargs):
        # fprint(f"Fleche.__init__({name})")
        super().__init__()

        self.name = name
        self.color = color
        self.coords = pygame.Rect(coords)
        self.args = args

        self.callback = kwargs.get("callback")

        self.largeur: int = coords[2] // 20
        self.nb_fleches = 10
        self.diff = 100 // self.nb_fleches
        self.total = self.largeur * (self.nb_fleches - 1)

    def mouse_click(self):
        # fprint(f"Fleche {self.name!r} Clicked")
        if self.callback:
            self.callback()

    def draw(self):
        if self.hidden:
            return

        ym = self.coords.midleft[1]
        dh = self.coords[3] // 2
        yh = ym - dh
        yb = ym + dh
        
        for c in range(self.nb_fleches):
            larg_c = self.largeur * c
            dc = 105 + self.diff * c

            if self.mouse_clicking:
                color = (dc, dc, dc)
            elif self.mouse_over:
                color = (0, dc, 0)
            else:
                color = (0, dc, dc)

            if self.args[0] == "RIGHT":
                x2g = self.coords.midtop[0] - larg_c
                x2d = self.coords.midright[0] - larg_c

            else:
                x2g = self.coords.midtop[0] + self.total - larg_c
                x2d = self.coords.midleft[0] + self.total - larg_c

            pygame.draw.line(self.screen, color, (x2g, yh), (x2d, ym), self.largeur)
            pygame.draw.line(self.screen, color, (x2g, yb), (x2d, ym), self.largeur)
        
        # pygame.draw.rect(self.screen, (255, 0, 0), (self.coords), 1)


class Commandes:

    def __init__(self):
        self.lst: list[Commande] = list()

    def count(self, objet: type) -> int:
        return len(list(filter(lambda x: x.__class__ is objet, self.lst)))

    def add(self, cmd: Commande):
        self.lst.append(cmd)

    def pop(self):
        return self.lst.pop()

    def last(self) -> Optional[Commande]:
        if self.lst:
            return self.lst[-1]

        return None

    def clear(self):
        self.lst.clear()

    def get(self, name: str) -> Optional[Commande]:
        for cmd in self.lst:
            if cmd.name == name:
                return cmd

        return None

    def mouse_move(self, mouse_position: tuple):
        for cmd in self.lst:
            cmd.mouse_move(mouse_position)

    def mouse_down(self):
        for cmd in self.lst:
            cmd.mouse_down()

    def mouse_up(self):
        for cmd in self.lst:
            cmd.mouse_up()

    def update(self):
        for cmd in self.lst:
            cmd.update()

    def draw(self):
        for cmd in self.lst:
            cmd.draw()


class Main:

    def __init__(self):
        pygame.init()

        Variable.SYS_FONT16 = pygame.font.SysFont("arial", 16)
        Variable.SYS_FONT18 = pygame.font.SysFont("arial", 18)
        Variable.SYS_FONT20 = pygame.font.SysFont("arial", 20)
        Variable.SYS_FONT22 = pygame.font.SysFont("arial", 22)
        Variable.SYS_FONT24 = pygame.font.SysFont("arial", 24)

        self.screen = pygame.display.set_mode((1210, 750), pygame.RESIZABLE, 32)
        Commande.SCREEN = self.screen

        self.screen_width, self.screen_height = self.screen.get_size()
        self.image_posx = 0
        self.image_posy = 0
        self.updating = None
        self.running = True
        self.ecran = 0
        self.mouse_pos_x, self.mouse_pos_y = 0, 0

        self.emplacementid = 0
        self.emplacement = ""

        self.ident_min = 1
        self.ident_max = 1
        self.ident = self.ident_min

        self.index = 0
        self.nb_images = 0

        self.offset = 0
        self.offset_max = 0
        self.limit = 0

        self.cmds = Commandes()
        self.load_database()
        self.load_ecran(1)

    def get_fonts(self):
        liste_polices = pygame.font.get_fonts()
        # 3. Trier la liste par ordre alphabétique (optionnel, mais plus propre)
        liste_polices.sort()

        # 4. Afficher les polices
        print(f"Nombre de polices trouvées : {len(liste_polices)}\n")
        for police in liste_polices:
            print(police)

    def load_database(self):
        self.msl = MySQL(Variable.DATABASE_NAME)
        self.msl.create_table()
        # self.msl.read_files()
        apres = self.msl.count_table("pictures")
        self.nb_collections = self.msl.count_table("repertoires")
        fprint(apres, "image(s) présente(s) dans", self.nb_collections, "collections")

    def init_datas(self, emplacementid: int = 0):
        if self.ecran == 1:
            pygame.display.set_caption("Liste des répertoires")

            xmax = (self.screen_width - 20) // 170
            ymax = (self.screen_height - 70) // 220
            self.limit = xmax * ymax
            if self.nb_collections <= self.limit:
                self.offset_max = 0
            else:
                self.offset_max = ((self.nb_collections-1) // self.limit) * self.limit

        elif self.ecran == 2:
            self.emplacementid = emplacementid
            sql = """
                SELECT emplacement
                FROM repertoires
                WHERE emplacementid = :emplacementid
            """
            row = self.msl.select_one(sql, {"emplacementid": emplacementid})
            self.emplacement = f"{row.emplacement}"
            pygame.display.set_caption(self.emplacement)

            # Footer
            taille = (self.screen_width, 40)
            self.footer_position = (0, self.screen_height-taille[1])
            self.footer = pygame.Surface(taille, pygame.SRCALPHA)

            self.nb_images = self.msl.count_table("pictures", 
                where="emplacementid = :emplacementid", data={
                    "emplacementid": emplacementid
                })

            self.ident_min = self.get_min_image_ident()
            self.ident_max = self.get_max_image_ident()

            ident = self.get_last_saved_image()
            if ident is None:
                self.index = 1
                self.ident = self.ident_min
            elif ident < self.ident_min or ident > self.ident_max:
                self.index = 1
                self.ident = self.ident_min
            else:
                self.ident = ident
                self.index = self.msl.count_table("pictures", 
                    where="emplacementid = :emplacementid and ident <= :ident", 
                    data={
                        "emplacementid": self.emplacementid,
                        "ident": self.ident
                    })

    def get_directories(self):
        sql = """
        SELECT rep.emplacementid, emplacement, MIN(ident) ident, MIN(nom) nom, COUNT(*) nombre
        FROM pictures p 
        INNER JOIN repertoires rep ON p.emplacementid = rep.emplacementid
        GROUP BY rep.emplacementid, emplacement
        ORDER BY emplacement
        LIMIT :limit
        OFFSET :offset
        """

        rows = self.msl.select_all(sql, {"limit": self.limit, "offset": self.offset})
        return rows

    def load_directories(self):
        ident: int
        nom: str
        nombre: int
        emplacement: str

        # fprint(f"load_directories({self.offset, self.limit})")

        while self.cmds.last().__class__ is Image:
            self.cmds.pop()

        idy = 0
        idx = 0
        for row in self.get_directories():
            ident = row.ident
            nom = row.nom.split("-")[0]
            nombre = row.nombre
            emplacementid = row.emplacementid
            emplacement = row.emplacement
            img = Image(ident, nom, (0, 50, 50), (20+170*idx, 80+220*idy, 150, 200), 
                callback=self.load_ecran, params=(2, ),
                surface=self.get_image, nombre=nombre,
                emplacementid=emplacementid,
                emplacement=emplacement)
            self.cmds.add(img)

            # retour a la ligne si plus de place
            if 20+170*(1+idx) + 150 > self.screen_width - 20:
                idx = 0
                idy += 1
            else:
                idx += 1

    def first_directory(self):
        if self.offset == 0:
            return

        self.offset = 0
        self.cmds.get("Gauche").set_visible(False)

        self.load_directories()

        droite = self.cmds.get("Droite")
        if droite.hidden and self.offset < self.offset_max:
            droite.set_visible(True)

        # simulation du mouvement de la souris
        self.cmds.mouse_move((self.mouse_pos_x, self.mouse_pos_y))

    def previous_directory(self):
        if self.offset == 0:
            return

        self.offset -= self.limit
        if self.offset < 0:
            self.offset = 0

        if self.offset == 0:
            self.cmds.get("Gauche").set_visible(False)

        self.load_directories()

        droite = self.cmds.get("Droite")
        if droite.hidden and self.offset < self.offset_max:
            droite.set_visible(True)

        # simulation du mouvement de la souris
        self.cmds.mouse_move((self.mouse_pos_x, self.mouse_pos_y))

    def next_directory(self):
        if self.offset + self.limit >= self.nb_collections:
            return 

        self.offset += self.limit
        gauche = self.cmds.get("Gauche")
        if gauche.hidden and self.offset > 0:
            gauche.set_visible(True)

        self.load_directories()

        self.cmds.get("Droite").set_visible(self.offset < self.offset_max)

        # simulation du mouvement de la souris
        self.cmds.mouse_move((self.mouse_pos_x, self.mouse_pos_y))

    def last_directory(self):
        if self.offset + self.limit >= self.nb_collections:
            return 

        self.offset = self.offset_max

        gauche = self.cmds.get("Gauche")
        if gauche.hidden and self.offset > 0:
            gauche.set_visible(True)

        self.load_directories()

        self.cmds.get("Droite").set_visible(False)

        # simulation du mouvement de la souris
        self.cmds.mouse_move((self.mouse_pos_x, self.mouse_pos_y))

    def load_ecran(self, numero, *params):
        # fprint("load ecran", numero, params)
        self.ecran = numero
        self.cmds.clear()

        if numero == 1:
            if len(params) > 0 and params[0] == "BACK":
                # sauvegarde de la dernière image consultée
                self.save_last_image()

            halt = Box("Quitter", (0, 200, 200), (10, 10, 50, 50), 
                callback=self.stop_running)
            self.cmds.add(halt)

            # liste des directories
            refresh = Box("Refresh", (200, 20, 20), (self.screen_width-60, 10, 50, 50),
                callback=self.update_database, thread=True)
            self.cmds.add(refresh)

            precedente = Fleche("Gauche", (0, 200, 200), (
                80, 10, 50, 50), "LEFT",
                callback=self.previous_directory)
            if self.offset == 0:
                precedente.set_visible(False)

            self.cmds.add(precedente)

            suivante = Fleche("Droite", (0, 200, 200), (
                self.screen_width - 130, 10, 50, 50), "RIGHT",
                callback=self.next_directory)
            self.cmds.add(suivante)

            self.init_datas()
            self.load_directories()

            if self.offset + self.limit >= self.nb_collections:
                suivante.set_visible(False)

            # simulation du mouvement de la souris
            self.cmds.mouse_move((self.mouse_pos_x, self.mouse_pos_y))

        elif numero == 2:
            # Image du repertoire selectionne
            refresh = Box("Back", (0, 200, 200), (10, 10, 50, 50),
                callback=self.load_ecran, params=(1, "BACK"))
            self.cmds.add(refresh)

            halt = Box("Quitter", (0, 200, 200), (self.screen_width-60, 10, 50, 50), 
                callback=self.stop_running)
            self.cmds.add(halt)

            precedente = Fleche("Gauche", (0, 200, 200), (
                30, self.screen_height // 2 - 40, 80, 80), "LEFT", 
                callback=self.previous_image)
            self.cmds.add(precedente)

            suivante = Fleche("Droite", (0, 200, 200), (
                self.screen_width - 110, self.screen_height // 2 - 40, 80, 80), "RIGHT",
                callback=self.next_image)
            self.cmds.add(suivante)

            self.init_datas(*params)
            self.load_image(self.ident)

    def stop_running(self):
        self.running = False

    def update_database(self):
        if self.updating is None:
            self.cmds.get("Refresh").set_exec_color((200, 0, 0))
            self.updating = Thread(target=self.msl.add_file)
            self.updating.start()

    def get_min_image_ident(self) -> int:

        sql = """
        SELECT MIN(ident) ident
        FROM pictures  
        WHERE emplacementid = :emplacementid
        """

        row = self.msl.select_one(sql, {
            "emplacementid": self.emplacementid
            })

        ident_min = row.ident

        return ident_min

    def get_next_image_ident(self, nombre: int = 1) -> int:
        sql = """
        SELECT ident
        FROM pictures  
        WHERE emplacementid = :emplacementid
          AND ident > :ident
        ORDER BY ident
        LIMIT 1
        OFFSET :nombre
        """
        datas: dict = {
            "ident": self.ident,
            "emplacementid": self.emplacementid,
            "nombre": nombre-1
            }

        row = self.msl.select_one(sql, datas)
        
        return row.ident

    def get_previous_image_ident(self, nombre: int = 1) -> int:
        sql = """
        SELECT ident
        FROM pictures  
        WHERE emplacementid = :emplacementid
          AND ident < :ident
        ORDER BY ident DESC
        LIMIT 1
        OFFSET :nombre
        """

        row = self.msl.select_one(sql, {
            "ident": self.ident,
            "emplacementid": self.emplacementid,
            "nombre": nombre-1
            })

        return row.ident

    def get_max_image_ident(self) -> int:

        sql = """
        SELECT MAX(ident) ident
        FROM pictures  
        WHERE emplacementid = :emplacementid
        """

        row = self.msl.select_one(sql, {
            "emplacementid": self.emplacementid
            })

        return row.ident

    def check_fleches(self):
        left = self.cmds.get("Gauche")
        right = self.cmds.get("Droite")

        if self.ident <= self.ident_min and not left.hidden:
            left.set_visible(False)
        elif self.ident > self.ident_min and left.hidden:
            left.set_visible(True)

        if self.ident >= self.ident_max and not right.hidden:
            right.set_visible(False)
        elif self.ident < self.ident_max and right.hidden:
            right.set_visible(True)

    def first_image(self):
        if self.ident <= self.ident_min:
            return

        self.index = 1
        self.load_image(self.ident_min)

    def previous_image(self, nombre: int = 1):
        if self.ident <= self.ident_min:
            return

        if self.ident - nombre <= self.ident_min:
            nombre = self.ident - self.ident_min
        
        self.index -= nombre

        self.load_image(self.get_previous_image_ident(nombre))

    def next_image(self, nombre: int = 1):
        if self.ident >= self.ident_max:
            return

        if self.ident + nombre >= self.ident_max:
            nombre = self.ident_max - self.ident

        self.index += nombre
        
        self.load_image(self.get_next_image_ident(nombre))

    def last_image(self):
        if self.ident >= self.ident_max:
            return

        self.index = self.nb_images
        self.load_image(self.ident_max)

    def get_image(self, ident_image: int, size) -> Tuple[Optional[pygame.surface.Surface], int, int]:
        # fprint(f"select_img({ident_image})")
        info_image = self.msl.select_img(ident=ident_image)

        if info_image is None:
            fprint("Image:", ident_image, "introuvable dans la bdd", flush=True)
            return None, 0, 0

        emplacementid, emplacement, nom = info_image
        fichier = Path(emplacement) / nom
        if not fichier.exists():
            fprint("Image:", nom, "introuvable sur le disque", flush=True)
            return None, 0, 0

        with open(fichier) as fhandle:
            try:
                new_image = pygame.image.load(fhandle)
                w, h = new_image.get_size()

            except Exception as erreur:
                fprint(f"Erreur lors du chargement de l'image: {fichier}")
                fprint(erreur)
                return None, 0, 0

        coef: float = 1.0
        size_width, size_height = size

        if w/h > size_width/size_height and w != 0:
            coef = size_width / w
        elif h != 0:
            coef = size_height / h

        if coef != 1.0:
            width = int(w * coef)
            height = int(h * coef)
            new_image = pygame.transform.scale(new_image, (width, height))
            
            image_posx = (size_width - width) // 2
            image_posy = (size_height - height) // 2

        else:
            image_posx = 0
            image_posy = 0

        self.nom_surface = Variable.SYS_FONT24.render(f"{nom}", False, (200, 200, 0))

        compteur = f"{self.index:^5_} / {self.nb_images:^5_}".replace("_", " ")
        self.compteur_surf = Variable.SYS_FONT24.render(f"{compteur}", False, (200, 200, 0))
        tx, ty = self.compteur_surf.get_size()
        self.compteur_position = size_width - 10 - tx, 4

        return new_image, image_posx, image_posy

    def get_last_saved_image(self):

        sql = """
        SELECT pictureid ident
        FROM repertoires
        WHERE emplacementid = :emplacementid
        """

        row = self.msl.select_one(sql, {
            "emplacementid": self.emplacementid
            })

        if row is None:
            return None

        return row.ident

    def save_last_image(self):

        self.msl.update("repertoires", 
            update_data={
                "pictureid": self.ident
            }, 
            where_data={"emplacementid": self.emplacementid})

    def load_image(self, new_ident: int):
        # Chargement de l'image et des dimensions
        new_image, self.image_posx, self.image_posy = self.get_image(
            new_ident, (self.screen_width, self.screen_height))
        # new_image.set_alpha(255)

        if new_image is None:
            return

        self.ident = new_ident
        self.image_surface = new_image

        self.check_fleches()

    def resize(self):
        # fprint("resize", self.screen.get_size())
        self.screen_width, self.screen_height = self.screen.get_size()

        if self.ecran == 1:
            self.load_ecran(1)

        elif self.ecran == 2:
            self.cmds.get("Gauche").set_pos(30, self.screen_height // 2 - 40)
            self.cmds.get("Droite").set_pos(self.screen_width - 110, self.screen_height // 2 - 40)
            self.cmds.get("Quitter").set_pos(self.screen_width - 60, 10)
            self.load_image(self.ident)

            # Footer
            taille = (self.screen_width, 40)
            self.footer_position = (0, self.screen_height-taille[1])
            self.footer = pygame.Surface(taille, pygame.SRCALPHA)

    def mouse_move(self, event):
        self.cmds.mouse_move(event.pos)
        self.mouse_pos_x, self.mouse_pos_y = event.pos

    def mouse_button_up(self, event):
        if event.button == 1:
            self.cmds.mouse_up()

    def mouse_button_down(self, event):
        if event.button == 1:
            self.cmds.mouse_down()

    def gestion_fin_threads(self):
        if self.updating is None:
            return

        if not self.updating.is_alive():
            self.updating.join()
            self.updating = None
            refresh = self.cmds.get("Refresh")
            if refresh:
                refresh.callback_ended()

    def get_pygame_events(self):
        pygame_events: dict = {
            1: self.get_directory_events,
            2: self.get_pictures_events
        }
        pygame_events.get(self.ecran)()

    def get_directory_events(self):
        key_function: dict = {
            pygame.K_ESCAPE: (self.stop_running,),
            pygame.K_F5: (self.load_ecran, 1),
            pygame.K_UP: (self.first_directory,),
            pygame.K_HOME: (self.first_directory,),
            pygame.K_DOWN: (self.last_directory, ),
            pygame.K_END: (self.last_directory,),
            pygame.K_LEFT: (self.previous_directory,),
            pygame.K_RIGHT: (self.next_directory,),
        }

        type_event: dict = {
            pygame.QUIT: (self.stop_running,),
            pygame.WINDOWRESIZED: (self.resize,),
            pygame.KMOD_LGUI: (self.mouse_move, "EVENT"),
            pygame.MOUSEBUTTONUP: (self.mouse_button_up, "EVENT"),
            pygame.MOUSEBUTTONDOWN: (self.mouse_button_down, "EVENT"),
        }

        for event in pygame.event.get():

            result = type_event.get(event.type)
            if result:
                fonction, *params = result
                if fonction:
                    if params and params[0] == "EVENT":
                        fonction(event)
                    else:
                        fonction()

            elif event.type == pygame.KEYUP:
                results = key_function.get(event.key)
                if results:
                    fonction, *params = results
                    if fonction is not None:
                        fonction(*params)

    def get_pictures_events(self):
        key_function: dict = {
            pygame.K_ESCAPE: (self.load_ecran, 1, "BACK"),
            pygame.K_UP: (self.first_image,),
            pygame.K_HOME: (self.first_image,),
            pygame.K_DOWN: (self.last_image, ),
            pygame.K_END: (self.last_image,),
            pygame.K_LEFT: (self.previous_image,),
            pygame.K_RIGHT: (self.next_image,),
            pygame.K_PAGEUP: (self.previous_image, 10),
            pygame.K_PAGEDOWN: (self.next_image, 10),
        }

        type_event: dict = {
            pygame.QUIT: (self.stop_running,),
            pygame.WINDOWRESIZED: (self.resize,),
            pygame.KMOD_LGUI: (self.mouse_move, "EVENT"),
            pygame.MOUSEBUTTONUP: (self.mouse_button_up, "EVENT"),
            pygame.MOUSEBUTTONDOWN: (self.mouse_button_down, "EVENT"),
        }

        for event in pygame.event.get():

            result = type_event.get(event.type)
            if result:
                fonction, *params = result
                if fonction:
                    if params and params[0] == "EVENT":
                        fonction(event)
                    else:
                        fonction()

            elif event.type == pygame.KEYUP:
                results = key_function.get(event.key)
                if results:
                    fonction, *params = results
                    if fonction is not None:
                        fonction(*params)

                else:
                    fprint(get_pygame_const_name(event.type), 
                        get_pygame_const_name(event.key))

            # else:
            #     fprint(get_pygame_const_name(event.type))

    def draw(self):
        self.screen.fill((50, 20, 50))
        if self.ecran == 2:
            if self.image_surface:
                self.screen.blit(self.image_surface, (self.image_posx, self.image_posy))

            self.footer.fill((10, 10, 10, 128))
            self.footer.blit(self.nom_surface, (10, 4))
            self.footer.blit(self.compteur_surf, self.compteur_position)
            self.screen.blit(self.footer, self.footer_position)
        
        self.cmds.draw()
        pygame.display.update()

    def run(self):
        while self.running:
            self.gestion_fin_threads()
            self.get_pygame_events()
            self.draw()

    def close(self):
        self.msl.close()
        pygame.quit()


if __name__ == "__main__":
    main = Main()
    try:
        main.run()
        main.close()

    except Exception as erreur:
        print(erreur)
        main.close()
        raise
