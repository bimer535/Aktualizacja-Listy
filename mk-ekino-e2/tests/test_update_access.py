import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import Mock
from test_gui import load_ui

class UpdateAccessTests(TestCase):
    def setUp(self):
        self.ui=load_ui();self.session=Mock()
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.ui.watchstate.PATH=Path(temporary.name)/'library.json'
        self.screen=self.ui.MKEkino(self.session)
        self.addCleanup(self.screen.cleanup)
    def test_menu_opens_updates_from_list(self):
        self.screen.options()
        self.assertIn(('Sprawdź aktualizację','updates'),self.session.openWithCallback.call_args.kwargs['list'])
        self.screen.option_selected(('Sprawdź aktualizację','updates'))
        self.session.open.assert_called_with(self.ui.Updates)
    def test_menu_returns_to_tiles_after_updates(self):
        self.screen.option_selected(('Sprawdź aktualizację','updates'),True)
        callback,screen=self.session.openWithCallback.call_args.args
        self.assertEqual(callback,self.screen.maybe_grid)
        self.assertIs(screen,self.ui.Updates)
    def test_blue_in_tiles_routes_to_updater_and_returns(self):
        grid=self.ui.PosterGrid(self.session,[dict(title='Film',action='sources',url='https://ekino.ws/movie/show/example')])
        self.addCleanup(grid.cleanup);grid.close=Mock()
        grid['actions'].actions['blue']()
        grid.close.assert_called_with(('updates',0))
        self.screen.tile_selected(('updates',0))
        callback,screen=self.session.openWithCallback.call_args.args
        self.assertIs(screen,self.ui.Updates)
        self.assertEqual(callback,self.screen.maybe_grid)
    def test_original_home_menu_and_four_card_view_restored(self):
        import catalogue
        self.assertEqual([e['action'] for e in catalogue.menu()],['categories','series','continue','favourites','versions','search','history'])
        grid=self.ui.PosterGrid(self.session,[]);self.addCleanup(grid.cleanup)
        self.assertEqual(len(grid.decoders),4)
        self.assertNotIn('panorama',grid.skin)
