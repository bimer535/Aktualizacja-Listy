from unittest import TestCase
from unittest.mock import Mock
from xml.etree import ElementTree as ET
from test_gui import load_ui

class RemoteFooterTests(TestCase):
    def setUp(self):self.ui=load_ui();self.session=Mock()
    def test_four_shortcuts_have_separate_rows_and_colored_symbols(self):
        grid=self.ui.PosterGrid(self.session,[]);self.addCleanup(grid.cleanup)
        expected={'red_key':'Wyjdź','yellow_key':'Lista / kafelki','blue_key':'Aktualizacja','menu_key':'Opcje'}
        for name,text in expected.items():self.assertEqual(grid[name].text,text)
        root=ET.fromstring(grid.skin);widgets={w.get('name'):w for w in root.findall('widget')}
        rectangles=[]
        for name in expected:
            w=widgets[name];x,y=map(int,w.get('position').split(','));width,height=map(int,w.get('size').split(','))
            self.assertGreaterEqual(y,610);self.assertLessEqual(y+height,650);self.assertLessEqual(x+width,1200)
            rectangles.append((x,x+width))
        for (_,end),(start,_) in zip(rectangles,rectangles[1:]):self.assertLess(end,start)
        colors={e.get('backgroundColor') for e in root.findall('eLabel')}
        self.assertTrue({'#ef596e','#ffd45a','#50b6ff'}<=colors)
        self.assertNotIn('\n',grid['hint'].text)
        self.assertEqual(grid['menu_badge'].text,'MENU')
    def test_red_closes_application_even_inside_category(self):
        screen=self.ui.MKEkino(self.session);self.addCleanup(screen.cleanup)
        screen.stack=[({'action':'main'},[],0)];screen.close=Mock();screen.back=Mock()
        # ActionMap holds the actual close method at construction time.
        self.assertEqual(screen['actions'].actions['red'].__name__,'close')
        screen.tile_selected(('exit',0));screen.close.assert_called_once_with();screen.back.assert_not_called()
    def test_tile_shortcuts_match_actual_remote_actions(self):
        grid=self.ui.PosterGrid(self.session,[]);self.addCleanup(grid.cleanup);grid.close=Mock()
        for key,route in [('red','exit'),('yellow','list'),('blue','updates'),('menu','options'),('cancel','back')]:
            grid['actions'].actions[key]();grid.close.assert_called_with((route,0))
