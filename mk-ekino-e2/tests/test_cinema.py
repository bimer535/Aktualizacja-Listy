import sys
from pathlib import Path
import unittest
from unittest.mock import Mock
from xml.etree import ElementTree as ET
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src/MKEkinoE2'))
from cinema_data import enrich, panorama, image_url
from design import grid_skin, description_skin
from test_gui import load_ui

WIDE='https://image.tmdb.org/t/p/w1280/abc.jpg'
class CinemaTests(unittest.TestCase):
    def test_panorama_never_falls_back_to_posters_or_older_films(self):
        entries=[dict(action='sources',year='2026',title='A',backdrop=WIDE),dict(action='sources',year='2025',backdrop=WIDE),dict(action='sources',year='2026',icon=WIDE),dict(action='next',year='2026',backdrop=WIDE)]
        self.assertEqual(panorama(entries),entries[:1])
    def test_matching_requires_title_and_year(self):
        entries=[dict(title='Film - HD',year='2026'),dict(title='Film',year='1999')]
        enrich(entries,[dict(key='film',year='2026',backdrop=WIDE)])
        self.assertEqual(entries[0]['backdrop'],WIDE)
        self.assertNotIn('backdrop',entries[1])
    def test_external_and_query_images_are_not_used(self):
        for value in ['https://example.com/p.jpg',WIDE+'?url=http://localhost','http://image.tmdb.org/t/p/w1280/a.jpg']:
            self.assertEqual(image_url(value,True),'')
    def test_home_navigation_and_selected_panorama_agree(self):
        ui=load_ui()
        rows=[dict(action='sources',year='2026',title=str(i),backdrop=WIDE.replace('abc',str(i))) for i in range(3)]
        grid=ui.PosterGrid(Mock(),rows,context={'action':'main'})
        grid.close=Mock();grid.layout_finished();grid.direction(1);grid.choose()
        grid.close.assert_called_with(('select',1))
        grid.up();grid.direction(2);grid.choose()
        grid.close.assert_called_with(('route',2))
        grid.down();grid.down();grid.close.assert_called_with(('expand',1))
        grid.cleanup()
    def test_closing_grid_removes_native_callbacks(self):
        ui=load_ui();grid=ui.PosterGrid(Mock(),[],context={'action':'main'})
        decoders=grid.decoders+[grid.wide_decoder]
        grid.cleanup()
        self.assertTrue(grid.closed)
        self.assertTrue(all(not d.PictureData.get() for d in decoders))
    def test_full_description_preserves_every_character(self):
        ui=load_ui();text='Pełny opis filmu. '*200
        screen=ui.FullDescription(Mock(),'Film',text)
        self.assertEqual(screen['body'].text,text)
        self.assertIn('down',screen['actions'].actions)
    def test_scaled_header_and_catalogue_stay_inside_osd(self):
        for dimensions in [(1280,720),(1920,1080)]:
            for mode in ['catalogue','sources','seasons']:
                skin=ET.fromstring(grid_skin(mode,dimensions))
                for widget in skin.findall('widget'):
                    x,y=map(int,widget.get('position').split(','));w,h=map(int,widget.get('size').split(','))
                    self.assertLessEqual(x+w,dimensions[0],widget.get('name'))
                    self.assertLessEqual(y+h,dimensions[1],widget.get('name'))
            ET.fromstring(description_skin(dimensions))
if __name__=='__main__':unittest.main()
