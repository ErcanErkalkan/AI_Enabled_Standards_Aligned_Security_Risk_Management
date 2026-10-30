"""Four dependency-light structural unit tests on the canonical XMI in repo.
This does not re-run archived Papyrus or Enterprise Architect GUI experiments.
"""
import sys
import tempfile
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[2]
sys.path.insert(0,str(HERE))
import check_typed_interop as oracle

XMI=REPO/'software/data/uml_schema.xmi'

def named(root,tag,name):
 for e in root.iter():
  if e.tag.rsplit('}',1)[-1]==tag and e.get('name')==name:return e
 raise AssertionError(f'missing {tag}: {name}')

class TypedSmoke(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.ref=oracle.load(XMI)
 def mutate(self,update,match):
  with tempfile.TemporaryDirectory() as d:
   tree=ET.parse(XMI);update(tree.getroot())
   out=Path(d)/'mutated.xmi';tree.write(out,encoding='utf-8',xml_declaration=True)
   diffs=oracle.diff(self.ref,oracle.load(out))
   self.assertTrue(any(match in x for x in diffs),diffs)
 def test_canonical_self(self):self.assertEqual([],oracle.diff(self.ref,oracle.load(XMI)))
 def test_association_target_mutation(self):
  def mut(root):named(named(root,'packagedElement','StandardToMetric'),'ownedEnd','metrics').set('type','Class_GQMGoal')
  self.mutate(mut,'associations.StandardToMetric.metrics')
 def test_attribute_type_mutation(self):
  def mut(root):named(named(root,'packagedElement','StandardRow'),'ownedAttribute','standardId').set('type','PT_Integer')
  self.mutate(mut,'classes.StandardRow.standardId')
 def test_generalization_mutation(self):
  def mut(root):
   c=named(root,'packagedElement','AssetValue');g=next(e for e in c if e.tag.rsplit('}',1)[-1]=='generalization');g.set('general','Class_GQMGoal')
  self.mutate(mut,'generalizations:')

if __name__=='__main__': unittest.main(verbosity=2)
