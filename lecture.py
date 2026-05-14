import sqlite3
import pygame

from pathlib import Path
from typing import Optional, Tuple, Callable
from collections import namedtuple
from threading import Thread


def fprint(*args, **kwargs):
    kwargs.pop("flush", 0)
    print(*args, **kwargs, flush=True)


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

    def count_table(self, tablename: str, where: Optional[str] = None) -> int:
        sql = "SELECT count(1) as nombre FROM " + tablename
        if where is not None:
            sql += "WHERE " + where

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

    def file_exists(self, nom: str, cursor) -> bool:

        sql = "SELECT nom FROM pictures WHERE nom = :nom"
        # requete = self.cu.execute(sql, {"nom": nom})
        requete = cursor.execute(sql, {"nom": nom})
        result = requete.fetchone()

        if result is None:
            return False

        return len(result) > 0

    def add_file(self):
        nombre: int = 0
        rep_init = Path("img")

        fprint("Updating Database: ...")
        myBd = sqlite3.connect("test.db")
        myCursor = myBd.cursor()

        for entrees in rep_init.walk("*.*"):
            root, dirs, files = entrees
            for fichier in files:
                if fichier.split(".")[1].lower() not in ("jpg", 
                "bmp", "webp", "gif", "jpeg"):
                    # ce n'est pas une image
                    continue

                # if self.file_exists(fichier):
                if self.file_exists(fichier, myCursor):
                    # Fichier déjà présent.
                    continue

                nombre += 1
                sql = """INSERT INTO pictures (emplacement, nom, img) 
                         VALUES (:emplacement, :nom, :data) """
                myCursor.execute(sql, 
                    {"emplacement": f"{root}", "nom": fichier, "data": None})

        myBd.commit()
        myBd.close()
        fprint(nombre, "fichier(s) ajouté(s)")

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

    def select_img(self, ident=None, nom=None):
        # 2. Récupération des informations de l'image
        if ident is not None:
            self.cu.execute("""
                SELECT emplacement, nom, img 
                FROM pictures 
                WHERE ident = :ident""", 
                {"ident": ident})

        elif nom is not None:
            self.cu.execute("""
                SELECT emplacement, nom, img 
                FROM pictures 
                WHERE nom like :nom""", 
                {"nom": f"{nom}%"})

        row = self.cu.fetchone()

        if row is None:
            return None

        return (row.emplacement, row.nom)


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

        self.coords = pygame.Rect(coords)
        self.args = args
        self.callback_ended()

        self.callback = kwargs.get("callback")
        self.thread = kwargs.get("thread", False)

    def set_exec_color(self, color: Tuple[int, int, int]):
        self.exec_color = color

    def mouse_click(self):
        # fprint(f"Box {self.name!r} Clicked")
        if self.callback and not self.executing_callback:
            self.executing_callback = self.thread
            self.callback()
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
                pygame.draw.rect(self.screen, self.exec_color, self.coords)
        else:
            pygame.draw.rect(self.screen, self.color, self.coords)


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

        self.largeur: int = 4
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
        yh = ym - 40
        yb = ym + 40
        
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


class Commandes:

    def __init__(self):
        self.lst: list[Commande] = list()

    def add(self, cmd: Commande):
        self.lst.append(cmd)

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
        self.screen = pygame.display.set_mode((1280, 768), pygame.RESIZABLE, 24)
        Commande.SCREEN = self.screen

        self.screen_width, self.screen_height = self.screen.get_size()
        self.image_posx = 0
        self.image_posy = 0
        self.updating = None
        self.running = True
        self.ecran = 0

        self.cmds = Commandes()
        self.load_database()
        self.load_ecran(1)

    def load_database(self):
        self.msl = MySQL("test.db")
        self.msl.create_table()
        # self.msl.read_files()
        apres = self.msl.count_table("pictures")
        fprint(apres, "image(s) présente(s)")

    def init_datas(self):
        if self.ecran == 2:
            self.image_pattern = "3934666-"  # Tsunade
            self.image_pattern = "3874743-"  # D.E.B.T
            self.image_pattern = "3882709-"  # High school pleasure Ep.3

            self.index_min = self.get_min_image_index()
            self.index_max = self.get_max_image_index()
            fprint(self.index_min, "< index <", self.index_max)
            self.index = self.index_min

    def load_ecran(self, numero):
        self.ecran = numero
        self.cmds.clear()

        if numero == 1:
            halt = Box("Fermer", (0, 200, 200), (self.screen_width-60, 10, 50, 50), 
                callback=self.stop_running)
            self.cmds.add(halt)

        elif numero == 2:
            refresh = Box("Refresh", (0, 200, 200), (10, 10, 50, 50),
                callback=self.update_database, thread=True)
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

            self.init_datas()
            self.load_image(self.index)

    def stop_running(self):
        self.running = False

    def update_database(self):
        if self.updating is None:
            self.cmds.get("Refresh").set_exec_color((200, 0, 0))
            self.updating = Thread(target=self.msl.add_file)
            self.updating.start()

    def get_min_image_index(self) -> int:

        sql = """
        SELECT nom
        FROM pictures  
        WHERE nom like :filename
            AND LENGTH(nom) = (
            SELECT MIN(LENGTH(nom))
            FROM pictures
            WHERE nom like :filename) 
        ORDER BY nom
        """

        row = self.msl.select_one(sql, {"filename": f"{self.image_pattern}%"})
        index_max = int(row.nom.split(".")[0].split("-")[1])

        return index_max

    def get_max_image_index(self) -> int:

        sql = """
        SELECT nom
        FROM pictures  
        WHERE nom like :filename
            AND LENGTH(nom) = (
            SELECT MAX(LENGTH(nom))
            FROM pictures
            WHERE nom like :filename) 
        ORDER BY nom DESC
        """
        row = self.msl.select_one(sql, {"filename": f"{self.image_pattern}%"})
        index_max = int(row.nom.split(".")[0].split("-")[1])

        return index_max

    def check_fleches(self):
        left = self.cmds.get("Gauche")
        right = self.cmds.get("Droite")

        if self.index <= self.index_min and not left.hidden:
            left.set_visible(False)
        elif self.index > self.index_min and left.hidden:
            left.set_visible(True)

        if self.index >= self.index_max and not right.hidden:
            right.set_visible(False)
        elif self.index < self.index_max and right.hidden:
            right.set_visible(True)

    def first_image(self):
        if self.index <= self.index_min:
            return
        self.load_image(self.index_min)

    def previous_image(self):
        if self.index <= 1:
            return
        self.load_image(self.index-1)

    def next_image(self):
        if self.index >= self.index_max:
            return
        self.load_image(self.index+1)

    def last_image(self):
        if self.index >= self.index_max:
            return
        self.load_image(self.index_max)

    def load_image(self, new_index: int):
        nom_image = f"{self.image_pattern}{new_index}."
        info_image = self.msl.select_img(nom=nom_image)

        if info_image is None:
            fprint("Image:", nom_image, "introuvable dans la bdd", flush=True)
            return None

        emplacement, nom = info_image
        fichier = Path(emplacement) / nom
        if not fichier.exists():
            fprint("Image:", nom, "introuvable sur le disque", flush=True)
            return None

        with open(fichier) as fhandle:
            try:
                new_image = pygame.image.load(fhandle)
                w, h = new_image.get_size()

            except Exception as erreur:
                fprint("Erreur lors du chargement de l'image:")
                fprint(erreur)

        coef: float = 1.0
        dw = self.screen_width - w
        dh = self.screen_height - h

        if dw < 0 or dh < 0:
            if dw > dh:
                coef = self.screen_height / h
            else:
                coef = self.screen_width / w
        elif dw > dh:
            coef = self.screen_height / h
        else:
            coef = self.screen_width / w

        if coef != 1.0:
            width = int(w * coef)
            height = int(h * coef)
            new_image = pygame.transform.scale(new_image, (width, height))
            
            self.image_posx = (self.screen_width - width) // 2
            self.image_posy = (self.screen_height - height) // 2

        else:
            self.image_posx = 0
            self.image_posy = 0

        # new_image.set_alpha(255)
        self.screen.fill((30, 20, 30))

        self.index = new_index
        self.image_surface = new_image
        self.check_fleches()

    def resize(self):
        # fprint("resize", self.screen.get_size())
        self.screen_width, self.screen_height = self.screen.get_size()
        self.cmds.get("Gauche").set_pos(30, self.screen_height // 2 - 40)
        self.cmds.get("Droite").set_pos(self.screen_width - 110, self.screen_height // 2 - 40)
        self.cmds.get("Fermer").set_pos(self.screen_width - 60, 10)
        self.load_image(self.index)

    def gestion_fin_threads(self):
        if self.updating is None:
            return

        if not self.updating.is_alive():
            self.updating.join()
            self.updating = None
            self.cmds.get("Refresh").callback_ended()

    def get_pygame_events(self):
        if self.ecran == 1:
            self.get_pygame_events_1()

        elif self.ecran == 2:
            self.get_pygame_events_2()

    def get_pygame_events_1(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False

            elif event.type == pygame.KEYUP:
                if event.key == pygame.K_ESCAPE:
                    self.running = False

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
                    self.running = False

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
