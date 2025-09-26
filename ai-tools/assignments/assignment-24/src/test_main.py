"""
Yksikkötestit InsaneMoneyHoboRobo-pelille.

Testaa Robo-, Kolikko- ja Hirvio-luokkien toimintaa sekä
handle_name_input- ja robot_hits_monster-funktioita.
Kattaa myös poikkeavat syötteet kuten unicode, pitkä merkkijono ja inf/NaN.
"""

import os
import sys
import unittest
import importlib
from unittest.mock import patch, Mock
import math

# Hiljennä Pygamen tervehdys ja käytä dummy-ajuria
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "hide")
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

GAME_MODULE_NAME = "main"
TEST_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = TEST_DIR
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

class _Surf:
    """
    Dummy pygame.Surface-mock, jolla voidaan määrittää leveys ja korkeus.
    """
    def __init__(self, w, h):
        self._w, self._h = w, h

    def get_width(self):
        return self._w

    def get_height(self):
        return self._h

def _mock_image_load(path):
    """
    Palauttaa mock-kuvan tiedostonimen perusteella.
    """
    name = os.path.basename(path).lower()
    if "kolikko" in name:
        return _Surf(40, 40)
    if "robo" in name:
        return _Surf(50, 86)
    if "hirvio" in name:
        return _Surf(50, 70)
    return _Surf(10, 10)

class PygamePatcher:
    """
    Mockkaa kaikki pygame-funktiot, joita testit tarvitsevat.
    """
    def __init__(self):
        self.patchers = []

    def start(self):
        self.patchers.append(patch("pygame.init", return_value=None))
        self.patchers.append(patch("pygame.display.set_caption", return_value=None))
        self.patchers.append(patch("pygame.display.set_mode", return_value=object()))
        self.patchers.append(patch("pygame.display.flip", return_value=None))
        self.patchers.append(patch("pygame.draw.rect", return_value=None))
        self.patchers.append(patch("pygame.image.load", side_effect=_mock_image_load))
        mock_clock = Mock()
        mock_clock.tick.return_value = None
        self.patchers.append(patch("pygame.time.Clock", return_value=mock_clock))
        self.patchers.append(
            patch("pygame.font.SysFont",
                  return_value=Mock(render=Mock(return_value=_Surf(120, 24))))
        )
        for p in self.patchers:
            p.start()

    def stop(self):
        for p in reversed(self.patchers):
            p.stop()

class DummyEvent:
    """
    Dummy Pygame event -mock, jolla voidaan testata näppäintapahtumia.
    """
    def __init__(self, type_=2, key=None, unicode=''):
        self.type = type_
        self.key = key
        self.unicode = unicode

class TestInsaneMoneyHoboRobo(unittest.TestCase):
    """
    Yksikkötestit pääsovelluksen funktioille ja luokille.
    """

    @classmethod
    def setUpClass(cls):
        """
        Asetetaan mock-pygame käyttöön ja ladataan pelimoduuli.
        """
        cls.pg = PygamePatcher()
        cls.pg.start()
        cls.game = importlib.import_module(GAME_MODULE_NAME)

    @classmethod
    def tearDownClass(cls):
        """
        Vapautetaan mock-pygame käytöstä.
        """
        cls.pg.stop()

    def test_handle_name_input_ascii(self):
        """
        Testaa nimen syöttöä ascii-merkeillä ja backspacella.
        """
        handle = self.game.handle_name_input
        name = ""
        for ch in "Testi123":
            e = DummyEvent(type_=2, key=ord(ch), unicode=ch)
            name = handle(name, e)
        self.assertEqual(name, "Testi123")
        # Backspace poistaa merkin
        e = DummyEvent(type_=2, key=8)  # pygame.K_BACKSPACE = 8
        name = handle(name, e)
        self.assertEqual(name, "Testi12")

    def test_handle_name_input_unicode_and_long(self):
        """
        Testaa nimen syöttöä Unicode-merkeillä ja pitkällä syötteellä.
        """
        handle = self.game.handle_name_input
        name = ""
        for ch in "李四زيد💰🤖":
            e = DummyEvent(type_=2, key=0, unicode=ch)
            name = handle(name, e)
        self.assertIn("李四", name)
        self.assertIn("زيد", name)
        # Pitkä syöte katkaistaan 32 merkkiin
        for _ in range(40):
            e = DummyEvent(type_=2, key=65, unicode="A")
            name = handle(name, e)
        self.assertLessEqual(len(name), 32)

    def test_handle_name_input_nonkey(self):
        """
        Testaa ettei nimi muutu, jos tapahtumatyyppi ei ole KEYDOWN.
        """
        handle = self.game.handle_name_input
        nimi = "test"
        e = DummyEvent(type_=999)
        self.assertEqual(handle(nimi, e), "test")

    def test_robo_move(self):
        """
        Testaa Robo-olion liikkeen eri suuntiin.
        """
        Robo = self.game.Robo
        r = Robo()
        x0, y0 = r.x, r.y
        r.liikuta("oikea")
        self.assertEqual(r.x, x0 + 2)
        r.liikuta("vasen")
        self.assertEqual(r.x, x0)
        r.liikuta("ylos")
        self.assertEqual(r.y, y0 - 2)
        r.liikuta("alas")
        self.assertEqual(r.y, y0)

    def test_robo_move_ignores_unknown_unicode_direction(self):
        """
        Testaa että tuntematon suunta (esim. unicode, emojit) ei liikuttele robottia.
        """
        Robo = self.game.Robo
        r = Robo()
        x0, y0 = r.x, r.y
        r.liikuta("左")
        r.liikuta("يمين")
        r.liikuta("mañana")
        r.liikuta("👍" * 10000)
        self.assertEqual((r.x, r.y), (x0, y0))

    def test_hirvio_bounce(self):
        """
        Testaa Hirvio-olion suunnan vaihtuminen reunoilla.
        """
        Hirvio = self.game.Hirvio
        h = Hirvio(950, 100)
        h.leveys = 50
        h.hirvio.get_width = lambda: 50
        h.x = 950
        h.vx = 2
        h.liikuta()
        self.assertEqual((h.vx, h.x), (-2, 948))
        h.x, h.vx = 0, -2
        h.liikuta()
        self.assertEqual((h.vx, h.x), (2, 2))

    def test_kolikko_bounds(self):
        """
        Testaa, että Kolikko-olio on aina ruudun rajoissa.
        """
        Kolikko = self.game.Kolikko
        for _ in range(50):
            k = Kolikko()
            self.assertGreaterEqual(k.x, 0)
            self.assertLessEqual(k.x, 1000 - k.leveys)
            self.assertGreaterEqual(k.y, 40)
            self.assertLessEqual(k.y, 500 - k.korkeus - 35)

    def test_robot_hits_monster_true_false(self):
        """
        Testaa robot_hits_monster: törmäys ja ei törmäystä.
        """
        robo = self.game.Robo()
        robo.x, robo.y, robo.leveys, robo.korkeus = 100, 100, 50, 50
        h = self.game.Hirvio(110, 110)
        h.x, h.y, h.leveys, h.korkeus = 110, 110, 50, 50
        self.assertTrue(self.game.robot_hits_monster(robo, [h]))
        # Ei törmäystä
        h2 = self.game.Hirvio(500, 500)
        h2.x, h2.y, h2.leveys, h2.korkeus = 500, 500, 50, 50
        self.assertFalse(self.game.robot_hits_monster(robo, [h2]))

    def test_robot_hits_monster_nan_inf(self):
        """
        Testaa, että robot_hits_monster ei kaadu NaN- tai inf-arvoilla.
        """
        robo = self.game.Robo()
        robo.x, robo.y = math.inf, math.nan
        robo.leveys, robo.korkeus = 50, 50
        h = self.game.Hirvio(0, 0)
        h.x, h.y = 0, 0
        h.leveys, h.korkeus = 50, 50
        # Ei pitäisi kaatua, vaan palauttaa False
        self.assertFalse(self.game.robot_hits_monster(robo, [h]))

if __name__ == "__main__":
    unittest.main(verbosity=2)
