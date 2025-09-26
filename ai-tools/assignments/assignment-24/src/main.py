# Images © 2018 Nygren, Leinonen & Agile Education Research group — Apache-2.0 (see LICENSE file)
"""
InsaneMoneyHoboRobo — Pygame-peli, jossa kerätään kolikoita ja vältetään hirviöitä.
Koodin omistaa tekijä, kuvat Apache-2.0.
"""

import pygame
from random import randint


def handle_name_input(current_name: str, tapahtuma) -> str:
    """
    Päivittää pelaajan nimeä yhden Pygame-tapahtuman perusteella.

    Args:
        current_name (str): Nykyinen pelaajan nimi.
        tapahtuma: Pygame event (KEYDOWN).

    Returns:
        str: Päivitetty nimi.
    """
    if tapahtuma.type != pygame.KEYDOWN:
        return current_name
    if tapahtuma.key == pygame.K_BACKSPACE:
        return current_name[:-1]
    if tapahtuma.key == pygame.K_RETURN:
        return current_name
    ch = getattr(tapahtuma, "unicode", "")
    if ch and len(current_name) < 32:
        return current_name + ch
    return current_name


def robot_hits_monster(robo, hirviot) -> bool:
    """
    Tarkistaa osuuko robo vähintään yhteen hirviöön.

    Args:
        robo: Robo-olio, jossa x, y, leveys, korkeus.
        hirviot (list): Lista Hirvio-olioita.

    Returns:
        bool: True jos törmäys, muuten False.
    """
    rx1, ry1 = robo.x, robo.y
    rx2, ry2 = robo.x + robo.leveys, robo.y + robo.korkeus
    for h in hirviot:
        hx1, hy1 = h.x, h.y
        hx2, hy2 = h.x + h.leveys, h.y + h.korkeus
        if rx1 < hx2 and rx2 > hx1 and ry1 < hy2 and ry2 > hy1:
            return True
    return False


class Robo:
    """
    Pelaajan robotti-hahmo.

    Attributes:
        robo (Surface): Robottikuva.
        x (int): X-koordinaatti.
        y (int): Y-koordinaatti.
        leveys (int): Kuvan leveys.
        korkeus (int): Kuvan korkeus.
    """

    def __init__(self) -> None:
        """Lataa kuvan ja alustaa koordinaatit."""
        self.robo = pygame.image.load("robo.png")
        self.x = 0
        self.y = 500 - self.robo.get_height()
        self.leveys = self.robo.get_width()
        self.korkeus = self.robo.get_height()

    def liikuta(self, suunta: str) -> None:
        """
        Liikuttaa robottia annettuun suuntaan.

        Args:
            suunta (str): 'vasen', 'oikea', 'ylos', 'alas'
        """
        if suunta == "vasen":
            self.x -= 2
        elif suunta == "oikea":
            self.x += 2
        elif suunta == "ylos":
            self.y -= 2
        elif suunta == "alas":
            self.y += 2


class Kolikko:
    """
    Kolikko-olio, joka sijoitetaan satunnaiseen paikkaan ruudulla.
    """

    def __init__(self) -> None:
        """Asettaa kolikon satunnaiseen sijaintiin."""
        self.kolikko = pygame.image.load("kolikko.png")
        self.x = randint(0, 1000 - self.kolikko.get_width())
        self.y = randint(40, 500 - self.kolikko.get_height() - 35)
        self.leveys = self.kolikko.get_width()
        self.korkeus = self.kolikko.get_height()


class Hirvio:
    """
    Hirviö-olio, joka liikkuu vaakasuunnassa ja kimpoaa reunoista.

    Attributes:
        x (int): X-koordinaatti.
        y (int): Y-koordinaatti.
        vx (int): Nopeus X-suunnassa.
    """

    def __init__(self, x: int, y: int) -> None:
        """Lataa kuvan ja asettaa sijainnin."""
        self.hirvio = pygame.image.load("hirvio.png")
        self.x = x
        self.y = y
        self.vx = 2
        self.leveys = self.hirvio.get_width()
        self.korkeus = self.hirvio.get_height()

    def liikuta(self) -> None:
        """Liikuttaa hirviötä ja vaihtaa suuntaa reunoilla."""
        if self.x + self.hirvio.get_width() == 1000:
            self.vx = -2
        elif self.x == 0:
            self.vx = 2
        self.x += self.vx


if __name__ == "__main__":
    # --- Pelin pääsilmukka ---
    pygame.init()
    pygame.display.set_caption("InsaneMoneyHoboRobo")
    leveys, korkeus = 1000, 500
    naytto = pygame.display.set_mode((leveys, korkeus))
    kello = pygame.time.Clock()

    robo = Robo()
    kolikko = Kolikko()
    hirviot = [Hirvio(i * 200, 50 + i * 75) for i in range(5)]
    pisteet = [0, 0]  # [hirviot, robo]

    player_name = ""
    peli_tila = False
    game_over = False

    fontti_otsikko = pygame.font.SysFont("calibri", 40)
    fontti_leipa = pygame.font.SysFont("calibri", 28)
    fontti = pygame.font.SysFont("calibri", 30)

    vasen = oikea = ylos = alas = False

    while True:
        for tapahtuma in pygame.event.get():
            if tapahtuma.type == pygame.QUIT:
                exit()
            if not peli_tila:
                player_name = handle_name_input(player_name, tapahtuma)
            if tapahtuma.type == pygame.KEYDOWN:
                if tapahtuma.key == pygame.K_LEFT:
                    vasen = True
                if tapahtuma.key == pygame.K_RIGHT:
                    oikea = True
                if tapahtuma.key == pygame.K_UP:
                    ylos = True
                if tapahtuma.key == pygame.K_DOWN:
                    alas = True
                if (tapahtuma.key == pygame.K_SPACE and
                        (not peli_tila) and player_name.strip()):
                    peli_tila = True
                if tapahtuma.key == pygame.K_F2:
                    pisteet = [0, 0]
                    peli_tila = False
                    game_over = False
                    player_name = ""
                    robo = Robo()
                    kolikko = Kolikko()
                    hirviot = [Hirvio(i * 200, 50 + i * 75) for i in range(5)]
            if tapahtuma.type == pygame.KEYUP:
                if tapahtuma.key == pygame.K_LEFT:
                    vasen = False
                if tapahtuma.key == pygame.K_RIGHT:
                    oikea = False
                if tapahtuma.key == pygame.K_UP:
                    ylos = False
                if tapahtuma.key == pygame.K_DOWN:
                    alas = False

        if not peli_tila:
            naytto.fill((64, 64, 64))
            punainen = (255, 0, 0)
            violetti = (255, 0, 255)
            tervetulo_teksti = fontti_otsikko.render(
                "Insane Money HoboRobo", True, punainen)
            ohjeet = fontti_leipa.render(
                "Syötä nimi ja paina SPACE aloittaaksesi.", True, punainen)
            nimi_ots = fontti_leipa.render("Syötä nimi:", True, punainen)
            nimi_val = fontti_leipa.render(player_name or "—", True, violetti)
            pygame.draw.rect(
                naytto, (255, 0, 0),
                pygame.Rect(2, 2, leveys - 4, korkeus - 4), 2)
            naytto.blit(
                tervetulo_teksti,
                (leveys / 2 - tervetulo_teksti.get_width() / 2, 30))
            naytto.blit(
                ohjeet,
                (leveys / 2 - ohjeet.get_width() / 2, 120))
            naytto.blit(
                nimi_ots,
                (leveys / 2 - nimi_ots.get_width() / 2, 200))
            naytto.blit(
                nimi_val,
                (leveys / 2 - nimi_val.get_width() / 2, 230))
            pygame.display.flip()
            kello.tick(15)
            continue

        if game_over:
            naytto.fill((0, 0, 0))
            teksti = fontti.render(
                "Game Over! Robotti törmäsi hirviöön.", True, (255, 0, 0))
            uusi_peli = fontti.render(
                "F2 - Uusi peli", True, (255, 255, 255))
            naytto.blit(
                teksti,
                (leveys / 2 - teksti.get_width() / 2,
                 korkeus / 2 - teksti.get_height() / 2 - 50))
            naytto.blit(
                uusi_peli,
                (leveys / 2 - uusi_peli.get_width() / 2,
                 korkeus / 2 - uusi_peli.get_height() / 2))
            pygame.display.flip()
            kello.tick(15)
            continue

        naytto.fill((102, 153, 102))
        for hirvio in hirviot:
            hirvio.liikuta()
        if vasen:
            robo.liikuta("vasen")
        if oikea:
            robo.liikuta("oikea")
        if ylos:
            robo.liikuta("ylos")
        if alas:
            robo.liikuta("alas")
        hirvio__pisteet = fontti.render(
            f"Kapitalistit: {pisteet[0]}", True, (51, 0, 51))
        robo__pisteet = fontti.render(
            f"Robotit: {pisteet[1]}", True, (51, 0, 51))
        for hirvio in hirviot:
            naytto.blit(hirvio.hirvio, (hirvio.x, hirvio.y))
        naytto.blit(robo.robo, (robo.x, robo.y))
        naytto.blit(kolikko.kolikko, (kolikko.x, kolikko.y))
        naytto.blit(hirvio__pisteet, (10, 10))
        naytto.blit(robo__pisteet, (200, 10))

        # --- Katkaise peli törmäyksestä! ---
        if robot_hits_monster(robo, hirviot):
            game_over = True

        # Kolikon keruu
        if kolikko.x in range(
            robo.x - (kolikko.leveys + 1),
            robo.x + 50 + (kolikko.leveys - 1)
        ):
            if kolikko.y in range(
                robo.y - kolikko.korkeus - 1,
                robo.y + robo.korkeus + kolikko.korkeus - 1
            ):
                pisteet[1] += 1
                kolikko = Kolikko()
        for hirvio in hirviot:
            if kolikko.x in range(
                hirvio.x - (kolikko.leveys + 1),
                hirvio.x + hirvio.leveys + (kolikko.leveys - 1)
            ):
                if kolikko.y in range(
                    hirvio.y - kolikko.korkeus - 1,
                    hirvio.y + hirvio.korkeus + kolikko.korkeus - 1
                ):
                    pisteet[0] += 1
                    kolikko = Kolikko()

        # Voittoehdot
        if pisteet[0] >= 25 or pisteet[1] >= 25:
            naytto.fill((0, 0, 0))
            if pisteet[0] == 25:
                teksti = fontti.render(
                    "Kapitalisti hirviöt voittivat, robotit jatkavat vallankumouksen suunnittelua!",
                    True, (0, 255, 255))
            else:
                teksti = fontti.render(
                    "Robotit voittivat. Koodarit saavuttavat maailmanherruuden!",
                    True, (0, 255, 255))
            uusi_peli = fontti.render(
                "F2 - Uusi peli", True, (0, 255, 255))
            naytto.blit(
                teksti,
                (leveys / 2 - teksti.get_width() / 2,
                 korkeus / 2 - teksti.get_height() / 2 - 50))
            naytto.blit(
                uusi_peli,
                (leveys / 2 - uusi_peli.get_width() / 2,
                 korkeus / 2 - uusi_peli.get_height() / 2))
            pygame.display.flip()
            kello.tick(15)
            continue

        pygame.display.flip()
        kello.tick(60)
