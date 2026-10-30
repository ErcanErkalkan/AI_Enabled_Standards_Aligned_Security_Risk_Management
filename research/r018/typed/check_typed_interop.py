#!/usr/bin/env python3
"""Audit a UML class-model XMI export against a reference using typed relationships.

Contract tested: named class/enumeration/primitive identities, class attributes and their
resolved types/cardinalities, association-end names/target types/cardinalities, resolved
generalization endpoints, ordered enum literals and normalized constraint language/body.
This is *structural/textual preservation*, not OCL semantic equivalence, instance-model
portability, standards semantic validation, or universal UML interoperability.
Serializer differences handled: arbitrary xmi:id, nested type idref vs type attribute,
missing optional LiteralInteger value => UML default zero, EA package wrappers, and
Papyrus test-created RoundTripSentinel_v021 class. EA's missing constraints are reported
as a known loss rather than silently normalized away.
"""
from __future__ import annotations
import argparse
from collections import Counter
from pathlib import Path
import json
import re
import sys
import xml.etree.ElementTree as ET


def local(tag):
    return tag.rsplit('}',1)[-1].rsplit(':',1)[-1]


def att(elem, name):
    return next((str(v) for k,v in elem.attrib.items() if local(k)==name), '')


def child(elem, name):
    return next((c for c in elem if local(c.tag)==name), None)


def bounds(elem):
    def read(name, default):
        c=child(elem,name)
        return (att(c,'value') or ('0' if name == 'lowerValue' else '1')) if c is not None else default
    return (read('lowerValue','1'), read('upperValue','1'))


def load(path: Path):
    root=ET.parse(path).getroot()
    typed={'uml:Class':'classes','uml:PrimitiveType':'primitives','uml:Enumeration':'enums',
           'uml:Association':'assocs','uml:Package':'packages'}
    named={k:{} for k in typed.values()}; ids={}; problems=[]
    for e in root.iter():
        if local(e.tag)=='packagedElement' and att(e,'type') in typed:
            kind=typed[att(e,'type')];name=e.attrib.get('name','')
            if not name: problems.append('unnamed '+kind);continue
            if name in named[kind]:problems.append(f'duplicate {kind}.{name}')
            named[kind][name]=e
            obj_id=att(e,'id')
            if obj_id:
                if obj_id in ids:problems.append('duplicate xmi:id '+obj_id)
                ids[obj_id]=(kind,name)
    def resolve_type(e):
        type_id=e.get('type','')
        if not type_id:
            ref=child(e,'type')
            if ref is not None:
                type_id=att(ref,'idref') or ref.attrib.get('href','')
        if not type_id:return '__MISSING_TYPE__'
        if type_id in ids:return ids[type_id][1]
        # External primitive references may use URI fragments. No guesswork about unknown IDs.
        if '#' in type_id:
            tail=type_id.split('#')[-1]
            if tail in ('String','Boolean','Integer','Real','UnlimitedNatural'):return tail
        problems.append('unresolved type '+type_id)
        return '__UNRESOLVED__:'+type_id
    owners={'classes':{}, 'assocs':{}, 'enums':{}}
    canonical_packages={'TraceabilityCore','SecurityContext'}
    def record_owners(e, parents=()):
        type_name=att(e,'type')
        if local(e.tag)=='packagedElement' and type_name=='uml:Package':
            if e.get('name') in canonical_packages:
                parents=parents+(e.get('name'),)
        if local(e.tag)=='packagedElement':
            kind=typed.get(type_name)
            if kind in owners:owners[kind][e.get('name','')]=list(parents)
        for c in e:record_owners(c,parents)
    record_owners(root)
    classes={}
    for name,e in named['classes'].items():
        attrs={}
        for a in e:
            if local(a.tag)!='ownedAttribute':continue
            key=a.attrib.get('name','')
            if not key or key in attrs:problems.append('duplicate/unnamed attribute '+name+'.'+key)
            attrs[key]={'type':resolve_type(a),'bounds':bounds(a)}
        classes[name]=attrs
    assoc={}
    for name,e in named['assocs'].items():
        ends={}
        for a in e:
            if local(a.tag)!='ownedEnd':continue
            key=a.attrib.get('name','')
            if not key or key in ends:problems.append('duplicate/unnamed end '+name+'.'+key)
            ends[key]={'target':resolve_type(a),'bounds':bounds(a)}
        assoc[name]=ends
    gens=[]
    # Parent map used to recover canonical specific end omitted in the source XMI.
    def walk(e,current_class=None):
        if local(e.tag)=='packagedElement' and att(e,'type')=='uml:Class':
            current_class=e.attrib.get('name','')
        if local(e.tag)=='generalization':
            general=ids.get(att(e,'general'),('','__UNRESOLVED_GENERAL__:'+att(e,'general')))[1]
            specific=ids.get(att(e,'specific'),('',current_class))[1] if att(e,'specific') else current_class
            if not current_class or general.startswith('__UNRESOLVED_') or not specific:
                problems.append('invalid generalization '+str(e.attrib))
            gens.append([specific,general])
        for c in e:walk(c,current_class)
    walk(root)
    # In the EA export a generalization may be located in class's model container.
    enumerations={name:[c.attrib.get('name','') for c in e if local(c.tag)=='ownedLiteral']
                  for name,e in named['enums'].items()}
    constraints={}
    for e in root.iter():
        if local(e.tag)!='ownedRule' or att(e,'type')!='uml:Constraint':continue
        name=e.get('name','')
        spec=child(e,'specification')
        lang='';body=''
        if spec is not None:
            lang=' '.join((c.text or '').strip() for c in spec if local(c.tag)=='language').strip()
            body=' '.join((c.text or '').strip() for c in spec if local(c.tag)=='body').strip()
        normalize=lambda s:re.sub(r'\s+',' ',s).strip()
        if name in constraints:problems.append('duplicate constraint '+name)
        constraints[name]={'language':normalize(lang),'body':normalize(body)}
    return {'classes':classes,'owners':owners,'associations':assoc,'generalizations':sorted(gens),
            'enumerations':enumerations,'primitives':sorted(named['primitives']),
            'packages':sorted(named['packages']), 'constraints':constraints,'problems':problems}


def diff(ref, got, allow_ea_wrappers=False, sentinel=None):
    out=[]
    for issue in got['problems']:out.append('parse-contract: '+issue)
    for field in ['classes','owners','associations','enumerations','primitives','generalizations','constraints','packages']:
        a=ref[field];b=got[field]
        if field=='classes' and sentinel:
            b={k:v for k,v in b.items() if k!=sentinel}
        if field=='owners' and sentinel:
            b={typ:{k:v for k,v in items.items() if k!=sentinel} for typ,items in b.items()}
        if field=='packages' and allow_ea_wrappers:
            b=[x for x in b if x not in ('StandardsTraceableSecurityEvidenceModel','EA_PrimitiveTypes_Package')]
        if isinstance(a,list):
            if sorted(a)!=sorted(b):out.append(f'{field}: expected {a}, observed {b}')
        elif isinstance(a,dict):
            akeys=set(a);bkeys=set(b)
            for k in sorted(akeys-bkeys):out.append(f'{field}.{k}: missing')
            for k in sorted(bkeys-akeys):out.append(f'{field}.{k}: unexpected')
            for k in sorted(akeys & bkeys):
                expected=a[k];observed=b[k]
                if not isinstance(expected,dict):
                    if expected!=observed:out.append(f'{field}.{k}: expected {expected!r}, observed {observed!r}')
                    continue
                ek=set(expected);ok=set(observed)
                for n in sorted(ek-ok):out.append(f'{field}.{k}.{n}: missing')
                for n in sorted(ok-ek):out.append(f'{field}.{k}.{n}: unexpected')
                for n in sorted(ek & ok):
                    if expected[n]!=observed[n]:out.append(f'{field}.{k}.{n}: expected {expected[n]!r}, observed {observed[n]!r}')
    return out


def main():
    pa=argparse.ArgumentParser(description=__doc__)
    pa.add_argument('--reference',type=Path,required=True)
    pa.add_argument('--candidate',type=Path,required=True)
    pa.add_argument('--ea-wrappers',action='store_true')
    pa.add_argument('--sentinel',default=None)
    pa.add_argument('--json-out',type=Path)
    args=pa.parse_args()
    try:
        ref=load(args.reference);cand=load(args.candidate)
        errors=diff(ref,cand,args.ea_wrappers,args.sentinel)
    except (ET.ParseError,OSError,ValueError) as exc:
        errors=[f'parse error: {type(exc).__name__}: {exc}'];ref={};cand={}
    status='PASS' if not errors else 'FAIL'
    counts={field:len(cand.get(field,[])) for field in ['classes','associations','primitives','enumerations','generalizations','constraints','packages']}
    report={'status':status,'reference':str(args.reference),'candidate':str(args.candidate),
            'scope':'typed UML class-model structure and textual constraints, NOT instance portability or semantic UML/OCL equivalence',
            'counts':counts, 'differences':errors, 'allow_ea_wrappers':args.ea_wrappers,
            'sentinel':args.sentinel}
    if args.json_out:
        args.json_out.parent.mkdir(exist_ok=True,parents=True)
        args.json_out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(status+' | '+str(len(errors))+' differences')
    for e in errors[:20]:print(' - '+e)
    if len(errors)>20:print(' ... additional',len(errors)-20,'differences in JSON')
    return 0 if not errors else 1

if __name__=='__main__':sys.exit(main())
