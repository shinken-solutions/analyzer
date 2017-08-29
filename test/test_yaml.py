#!/usr/bin/env python
# Copyright (C) 2014:
#    Gabes Jean, naparuba@gmail.com


from opsbro_test import *

import os
import sys
from opsbro.yamlmgr import yamler

'''
import opsbro.misc

p = os.path.join(os.path.dirname(opsbro.misc.__file__), 'internalyaml')
sys.path.insert(0, p)

import ruamel.yaml as yaml
'''


class TestYaml(OpsBroTest):
    def setUp(self):
        pass
    
    
    def test_yaml_load(self):
        s = '''# Pre comment
# on two lines
- super string # is this a valid comment
- k1: blabla
  k2: 36.000
  k3:
              # is this a valid comment
              - sub 1
              - sub 2
# ending comment
'''
        
        data = yamler.loads(s)
        
        self.assert_(data[0] == 'super string')
        self.assert_(data[1]['k1'] == 'blabla')
        self.assert_(data[1]['k2'] == 36.00)
        
        buf = yamler.dumps(data)
        print "BUF", buf

    def test_yaml_comments(self):
        s = '''# document comment line1
# document comment line2
key1: blabla  # key1 comment
        
# Key2 line before comment, part1
# Key2 line before comment, part2
key2: 36.000  # key2 same line comment
key3:  # key3 level comment
          # K3 sub list comment
          - entry key3.1  #key3.entry1 comment
          - sub 2
key4: 36
# ending comment
# ending comment bis
        '''
        data = yamler.loads(s)
        print "DATA", data, type(data), dir(data)
        #print 'DICT', data.__dict__
        #print data._yaml_format.__dict__
        #print data._yaml_line_col.__dict__
        
        print "CA", data.ca
        print "CA internals", data.ca.__dict__
        print "CA dir", dir(data.ca)
        print "CA.attrib", data.ca.attrib
        print "CA comment", data.ca.comment

        print "CA items", data.ca.items
        
        whole_data_comment = yamler.get_document_comment(data)
        print "Whole data comment", whole_data_comment
        whole_data_comment_OK = '''# document comment line1
# document comment line2'''
        self.assert_(whole_data_comment == whole_data_comment_OK)
        
        # Now check key1 comment
        key1_comment = yamler.get_key_comment(data, 'key1')
        print "KEY1 comment:", key1_comment
        key1_comment_OK = '# key1 comment'
        #self.assert_(key1_comment == key1_comment_OK)
        self.assertEqual(key1_comment, key1_comment_OK)
        
        # Key2 is a bit harder: got both lines before and same line comments
        key2_comment = yamler.get_key_comment(data, 'key2')
        print "KEY2 comment:", key2_comment
        key2_comment_OK = '''# Key2 line before comment, part1
# Key2 line before comment, part2
# key2 same line comment'''
        self.assertEqual(key2_comment, key2_comment_OK)
        
        # Key4: nothing, should be None
        key4_comment = yamler.get_key_comment(data, 'key4')
        print "KEY4 comment:", key4_comment
        self.assertIsNone(key4_comment)
        
        
if __name__ == '__main__':
    unittest.main()
