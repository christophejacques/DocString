import sqlite3
import pygame

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

    # DIRECTORY: str = r""
    # SUB_DIRECTORY: str = "img"

    DIRECTORY: str = r"F:\Images\Hentai"
    SUB_DIRECTORY: str = "."

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
      group_by: Optional[str] = None) -> int:

        if distinct:
            sql = f"SELECT count(distinct {distinct}) as nombre FROM " + tablename
        else:
            sql = "SELECT count(1) as nombre FROM " + tablename

        if where is not None:
            sql += " WHERE " + where

        if group_by is not None:
            sql += " GROUP BY " + group_by

        requete = self.cu.execute(sql)
        result = requete.fetchone()
        
        return result.nombre
        # return result[0]

    def create_table(self, drop_if_exists: bool = False):

        if drop_if_exists:
            self.cu.execute("DROP TABLE IF EXISTS pictures")

        self.cu.execute("""CREATE TABLE IF NOT EXISTS pictures(
            ident integer PRIMARY KEY AUTOINCREMENT,
            emplacement text,
            nom text,
            img blob
        )""")

    def file_exists(self, emplacement: str, nom: str, cursor) -> bool:

        sql = """
            SELECT nom 
            FROM pictures 
            WHERE nom = :nom
                AND emplacement = :emplacement
            """

        requete = cursor.execute(sql, {
            "emplacement": emplacement,
            "nom": nom
            })
        result = requete.fetchone()

        if result is None:
            return False

        return len(result) > 0

    def add_file(self):

        def walk_key_sort(e): 
            return e[0]

        nombre: int = 0
        rep_init = Path(Variable.SUB_DIRECTORY)

        fprint("Updating Database: ...")
        myBd = sqlite3.connect(Variable.DATABASE_NAME)
        myCursor = myBd.cursor()

        nb_files1 = 0

        for entrees in sorted(rep_init.walk(), key=walk_key_sort):
            root, dirs, files = entrees
            nb_files1 += len(files)

            for fichier in sorted(files):
                if fichier.split(".")[-1].lower() not in ("jpg", 
                "bmp", "webp", "gif", "jpeg", "png", "tiff"):
                    # ce n'est pas une image
                    print("Bad extension:", root, fichier)
                    continue

                # if self.file_exists(fichier):
                if self.file_exists(f"{root}", fichier, myCursor):
                    # Fichier déjà présent.
                    # print("File exists:", root, fichier)
                    continue

                nombre += 1
                sql = """INSERT INTO pictures (emplacement, nom, img) 
                         VALUES (:emplacement, :nom, :data) """
                myCursor.execute(sql, 
                    {"emplacement": f"{root}", "nom": fichier, "data": None})

        myBd.commit()
        myBd.close()
        fprint(nombre, "fichier(s) ajouté(s) sur", nb_files1, "trouvé(s)")

    def read_files(self):
        sql = "SELECT ident, nom FROM pictures"
        requete = self.cu.execute(sql)

        result = requete.fetchall()
        for index, fichier in enumerate(result):
            numero, nom = fichier
            print(f"{numero:5} {nom[:28]:28}", end="-")
            if index % 4 == 3:
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
                SELECT emplacement, nom, img 
                FROM pictures 
                WHERE ident = :ident""", 
                {"ident": ident})

        elif nom is not None:
            myCursor.execute("""
                SELECT emplacement, nom, img 
                FROM pictures 
                WHERE nom like :nom""", 
                {"nom": f"{nom}%"})

        row = myCursor.fetchone()
        emplacement = row.emplacement
        nom = row.nom

        myBd.close()

        if row is None:
            return None

        return (emplacement, nom)


def get_pygame_const_name(index):
    for c in dir(pygame):
        if callable(c):
            continue

        if c[0] in "AZERTYUIOPMLKJHGFDSQWXCVBN":
            if type(getattr(pygame, c)) is int and getattr(pygame, c) == index:
                return c

    return index


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
        self.header = pygame.Surface(taille, pygame.SRCALPHA)
        
        self.nb_surf = Variable.SYS_FONT20.render(f"{self.nombre}", False, (200, 200, 0))
        self.coords_nombre = (coords[0]+epaisseur, coords[1]+coords[3]-epaisseur-20)

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
            self.callback(*self.params, self.directory)

    def draw(self):
        if self.mouse_over:
            pygame.draw.rect(self.screen, 
                (self.color[0], 100, self.color[2]), self.coords)
        else:
            pygame.draw.rect(self.screen, self.color, self.coords)

        self.header.fill((10, 10, 10, 128))
        self.screen.blit(self.header, self.header_position)

        if self.image_surface:
            self.screen.blit(self.image_surface, self.coords_img[:2])
            self.screen.blit(self.nom_surf1, self.coords_nom1)

            if self.nom_surf2:
                self.screen.blit(self.nom_surf2, self.coords_nom2)

            if self.mouse_over:
                self.screen.blit(self.dir_surf, (200, 10))

        self.screen.blit(self.nb_surf, self.coords_nombre)


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

        self.emplacement = ""

        self.ident_min = 1
        self.ident_max = 1
        self.ident = self.ident_min

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
        self.nb_collections = self.msl.count_table("pictures", distinct="emplacement")
        fprint(apres, "image(s) présente(s) dans", self.nb_collections, "collections")

    def init_datas(self, emplacement):
        if self.ecran == 1:
            pass

        elif self.ecran == 2:
            self.emplacement = f"{emplacement}"

            self.ident_min = self.get_min_image_ident()
            self.ident_max = self.get_max_image_ident()
            # fprint(self.ident_min, "< ident <", self.ident_max)
            self.ident = self.ident_min

    def get_directories(self):
        sql = """
        SELECT emplacement, MIN(ident) ident, MIN(nom) nom, COUNT(*) nombre
        FROM pictures p 
        GROUP BY emplacement
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
            emplacement = row.emplacement
            img = Image(ident, nom, (0, 50, 50), (20+170*idx, 80+220*idy, 150, 200), 
                callback=self.load_ecran, params=(2, ),
                surface=self.get_image, nombre=nombre,
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

    def next_directory(self):
        if self.offset + self.limit >= self.nb_collections:
            return 

        self.offset += self.limit
        gauche = self.cmds.get("Gauche")
        if gauche.hidden and self.offset > 0:
            gauche.set_visible(True)

        self.load_directories()

        self.cmds.get("Droite").set_visible(self.offset < self.offset_max)

    def last_directory(self):
        if self.offset + self.limit >= self.nb_collections:
            return 

        self.offset = self.offset_max

        gauche = self.cmds.get("Gauche")
        if gauche.hidden and self.offset > 0:
            gauche.set_visible(True)

        self.load_directories()

        self.cmds.get("Droite").set_visible(False)

    def load_ecran(self, numero, *params):
        # fprint("load ecran", numero, params)
        self.ecran = numero
        self.cmds.clear()

        if numero == 1:
            refresh = Box("Refresh", (0, 200, 200), (10, 10, 50, 50),
                callback=self.update_database, thread=True)
            self.cmds.add(refresh)

            halt = Box("Fermer", (200, 20, 20), (self.screen_width-60, 10, 50, 50), 
                callback=self.stop_running)
            self.cmds.add(halt)

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

            xmax = (self.screen_width - 20) // 170
            ymax = (self.screen_height - 70) // 220
            self.limit = xmax * ymax
            if self.nb_collections <= self.limit:
                self.offset_max = 0
            else:
                self.offset_max = ((self.nb_collections-1) // self.limit) * self.limit

            self.load_directories()

            if self.offset + self.limit >= self.nb_collections:
                suivante.set_visible(False)

            # simulation du mouvement de la souris
            self.cmds.mouse_move((self.mouse_pos_x, self.mouse_pos_y))

        elif numero == 2:
            refresh = Box("Back", (0, 200, 200), (10, 10, 50, 50),
                callback=self.load_ecran, params=(1,))
            self.cmds.add(refresh)

            halt = Box("Fermer", (0, 200, 200), (self.screen_width-60, 10, 50, 50), 
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

            # Footer
            taille = (self.screen_width, 40)
            self.footer_position = (0, self.screen_height-taille[1])
            self.footer = pygame.Surface(taille, pygame.SRCALPHA)

            self.init_datas(*params)
            self.load_image(self.ident)

    def stop_running(self):
        self.running = False

    def update_database(self):
        if self.updating is None:
            self.cmds.get("Refresh").set_exec_color((200, 0, 0))
            self.updating = Thread(target=self.msl.add_file)
            self.updating.start()

    def get_min_image_ident(self, by_emplacement: bool = True) -> int:
        # fprint(f"get_min_image_ident({self.emplacement})")

        if by_emplacement:
            sql = """
            SELECT MIN(ident) ident
            FROM pictures  
            WHERE emplacement = :emplacement
            """

        else:
            sql = """
            SELECT nom, ident
            FROM pictures  
            WHERE nom like :filename
                AND LENGTH(nom) = (
                SELECT MIN(LENGTH(nom))
                FROM pictures
                WHERE nom like :filename) 
            ORDER BY nom
            """

        row = self.msl.select_one(sql, {
            "filename": "%-%",
            "emplacement": self.emplacement
            })

        # index_min = int(row.nom.split(".")[0].split("-")[1])
        ident_min = row.ident

        return ident_min

    def get_next_image_ident(self) -> int:
        sql = """
        SELECT MIN(ident) ident
        FROM pictures  
        WHERE emplacement = :emplacement
          AND ident > :ident
        """

        row = self.msl.select_one(sql, {
            "ident": self.ident,
            "emplacement": self.emplacement
            })

        return row.ident

    def get_previous_image_ident(self) -> int:
        sql = """
        SELECT MAX(ident) ident
        FROM pictures  
        WHERE emplacement = :emplacement
          AND ident < :ident
        """

        row = self.msl.select_one(sql, {
            "ident": self.ident,
            "emplacement": self.emplacement
            })

        return row.ident

    def get_max_image_ident(self, by_emplacement: bool = True) -> int:

        if by_emplacement:
            sql = """
            SELECT MAX(ident) ident
            FROM pictures  
            WHERE emplacement = :emplacement
            """

        else:
            sql = """
            SELECT nom, ident
            FROM pictures  
            WHERE nom like :filename
                AND LENGTH(nom) = (
                SELECT MAX(LENGTH(nom))
                FROM pictures
                WHERE nom like :filename) 
            ORDER BY nom DESC
            """

        row = self.msl.select_one(sql, {
            "filename": "%-%",
            "emplacement": self.emplacement
            })
        ident_max = row.ident

        return ident_max

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
        self.load_image(self.ident_min)

    def previous_image(self):
        if self.ident <= self.ident_min:
            return
        self.load_image(self.get_previous_image_ident())

    def next_image(self):
        if self.ident >= self.ident_max:
            return
        self.load_image(self.get_next_image_ident())

    def last_image(self):
        if self.ident >= self.ident_max:
            return
        self.load_image(self.ident_max)

    def get_image(self, ident_image: int, size) -> Tuple[Optional[pygame.surface.Surface], int, int]:
        # fprint(f"select_img({ident_image})")
        info_image = self.msl.select_img(ident=ident_image)

        if info_image is None:
            fprint("Image:", ident_image, "introuvable dans la bdd", flush=True)
            return None, 0, 0

        emplacement, nom = info_image
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

        return new_image, image_posx, image_posy

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
            self.cmds.get("Fermer").set_pos(self.screen_width - 60, 10)
            self.load_image(self.ident)

            # Footer
            taille = (self.screen_width, 40)
            self.footer_position = (0, self.screen_height-taille[1])
            self.footer = pygame.Surface(taille, pygame.SRCALPHA)

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
        if self.ecran == 1:
            self.get_pygame_events_1()

        elif self.ecran == 2:
            self.get_pygame_events_2()

    def get_pygame_events_1(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False

            elif event.type == pygame.WINDOWRESIZED:
                self.resize()

            elif event.type == pygame.KEYUP:
                if event.key == pygame.K_ESCAPE:
                    self.running = False

                elif event.key in (pygame.K_UP, pygame.K_HOME):
                    self.first_directory()

                elif event.key in (pygame.K_DOWN, pygame.K_END):
                    self.last_directory()

                elif event.key == pygame.K_LEFT:
                    self.previous_directory()

                elif event.key == pygame.K_RIGHT:
                    self.next_directory()

            elif event.type == pygame.KMOD_LGUI:
                self.cmds.mouse_move(event.pos)
                self.mouse_pos_x, self.mouse_pos_y = event.pos

            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self.cmds.mouse_down()

            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                self.cmds.mouse_up()

    def get_pygame_events_2(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False

            elif event.type == pygame.WINDOWRESIZED:
                self.resize()

            elif event.type == pygame.KEYDOWN:
                pass

            elif event.type == pygame.KEYUP:
                if event.key == pygame.K_ESCAPE:
                    # self.running = False
                    self.load_ecran(1)

                elif event.key in (pygame.K_UP, pygame.K_HOME):
                    self.first_image()

                elif event.key in (pygame.K_DOWN, pygame.K_END):
                    self.last_image()

                elif event.key == pygame.K_LEFT:
                    self.previous_image()

                elif event.key == pygame.K_RIGHT:
                    self.next_image()

                else:
                    fprint(get_pygame_const_name(event.type), 
                        get_pygame_const_name(event.key))

            elif event.type == pygame.KMOD_LGUI:
                self.cmds.mouse_move(event.pos)
                self.mouse_pos_x, self.mouse_pos_y = event.pos

            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self.cmds.mouse_down()

            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                self.cmds.mouse_up()

            else:
                pass
                # fprint(get_pygame_const_name(event.type))

    def draw(self):
        self.screen.fill((50, 20, 50))
        if self.ecran == 2:
            if self.image_surface:
                self.screen.blit(self.image_surface, (self.image_posx, self.image_posy))

            self.footer.fill((10, 10, 10, 128))
            self.footer.blit(self.nom_surface, (10, 4))
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
