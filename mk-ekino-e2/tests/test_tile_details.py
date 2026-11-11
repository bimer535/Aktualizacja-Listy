import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import Mock
from xml.etree import ElementTree as ET
from PIL import Image
from test_gui import load_ui

class TileDetailsTests(TestCase):
    def setUp(self):
        self.ui=load_ui();self.session=Mock()
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.ui.watchstate.PATH=Path(self.tmp.name)/'library.json'
    def test_default_tiles_migrated_once_without_losing_other_state(self):
        library=self.ui.watchstate.Library()
        self.assertEqual(library.settings()['view'],'tiles')
        library.write({'settings':{'view':'list','auto_play':False,'playback_service':4097},'favourites':[{'title':'Stored'}],'progress':{'key':{'position':20}}})
        screen=self.ui.MKEkino(self.session);self.addCleanup(screen.cleanup)
        self.assertEqual(screen.preferences['view'],'tiles')
        self.assertFalse(screen.preferences['auto_play'])
        self.assertEqual(screen.preferences['playback_service'],4097)
        self.assertEqual(library.read()['favourites'],[{'title':'Stored'}])
        self.assertEqual(library.read()['progress'],{'key':{'position':20}})
        library.setting('view','list');library.migrate_tile_default()
        self.assertEqual(library.settings()['view'],'list')
    def test_focus_wraps_exact_cover_bounds_above_artwork(self):
        grid=self.ui.PosterGrid(self.session,[]);self.addCleanup(grid.cleanup)
        widgets={w.get('name'):w for w in ET.fromstring(grid.skin).findall('widget')}
        for i in range(4):
            cover=widgets['cover%d'%i];mark=widgets['mark%d'%i]
            x,y=map(int,cover.get('position').split(','));mx,my=map(int,mark.get('position').split(','))
            self.assertEqual((mx+8,my+8),(x,y))
            self.assertEqual(mark.get('size'),'216,316')
            self.assertGreater(int(mark.get('zPosition')),int(cover.get('zPosition')))
            with Image.open(mark.get('pixmap')) as image:
                self.assertEqual(image.getpixel((108,158))[3],0)
                for point in [(108,4),(108,311),(4,158),(211,158)]:self.assertEqual(image.getpixel(point)[3],255)
    def test_next_page_uses_arrow_card_not_inherited_movie_poster(self):
        movie={'title':'Film','action':'sources','icon':'https://ekino.ws/static/thumb/a.jpg'}
        next_page={'title':'Następna strona','action':'page','pagination':True,'icon':movie['icon'],'url':'https://ekino.ws/movie/cat/strona[2]+'}
        grid=self.ui.PosterGrid(self.session,[movie,next_page]);self.addCleanup(grid.cleanup)
        grid.layout_finished();self.assertFalse(grid['next0'].visible);self.assertTrue(grid['next1'].visible)
        self.assertEqual(grid.current_url(1),'')
        grid.move(1);self.assertTrue(grid['mark1'].visible);self.assertFalse(grid['mark0'].visible)
        grid.close=Mock();grid.choose();grid.close.assert_called_with(('select',1))
        grid.entries=[movie];grid.page=-1;grid.index=0;grid.render();self.assertFalse(grid['next1'].visible)
    def test_correct_contact_and_four_original_cards(self):
        screen=self.ui.Contact(self.session);self.addCleanup(screen.cleanup)
        self.assertEqual(screen['email'].text,'bimer535@wp.pl')
        grid=self.ui.PosterGrid(self.session,[]);self.addCleanup(grid.cleanup)
        self.assertEqual(len(grid.decoders),4)
        self.assertNotIn('WYBRANO',grid.skin)
