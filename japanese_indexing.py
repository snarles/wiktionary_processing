import re
import json
import numpy as np

# obtained from https://github.com/tsroten/zhon/blob/main/src/zhon/hanzi.py
cjk_ideographs = (
    "\u3007"  # Ideographic number zero, see issue #17
    "\u4E00-\u9FFF"  # CJK Unified Ideographs
    "\u3400-\u4DBF"  # CJK Unified Ideographs Extension A
    "\uF900-\uFAFF"  # CJK Compatibility Ideographs
    "\U00020000-\U0002A6DF"  # CJK Unified Ideographs Extension B
    "\U0002A700-\U0002B73F"  # CJK Unified Ideographs Extension C
    "\U0002B740-\U0002B81F"  # CJK Unified Ideographs Extension D
    "\U0002F800-\U0002FA1F"  # CJK Compatibility Ideographs Supplement
)
radicals = "\u2F00-\u2FD5" "\u2E80-\u2EF3"

hirigana = "\u3040-\u309F"
katakana = "\u30A0-\u30FF" "\u31F0-\u31FF"

def find_kanjis_radicals_hirigana_katakana(query):
    kanjis = re.findall('[{}]'.format(cjk_ideographs), query)
    rads = re.findall('[{}]'.format(radicals), query)
    hir = re.findall('[{}]'.format(hirigana), query)
    kats = re.findall('[{}]'.format(katakana), query)
    return kanjis, rads, hir, kats

f_krhk = find_kanjis_radicals_hirigana_katakana

with open("languages/Japanese/wiktextract-data.jsonl", 'r') as file:
    jdict = {json.loads(l)["word"] : l for l in file.read().split('\n') if len(l) > 0}

with open("languages/Translingual/wiktextract-data.jsonl", 'r') as file:
    tdict = {json.loads(l)["word"] : l for l in file.read().split('\n') if len(l) > 0}

# find all kanjis in jdict!

all_kanjis = {}
prob_entries = {}
for k, v in jdict.items():
    kanjis, rads, hir, kat = f_krhk(v)
    for kanji in np.unique(kanjis):
        all_kanjis[kanji] = 1
        if kanji not in tdict.keys():
            prob_entries[kanji] = k

for k, v in prob_entries.items():
    print(k)
    print(json.loads(jdict[v]))
    print()

# kanjis used in jdict
kanjis = []
for kanji in all_kanjis.keys():
    if kanji in tdict.keys():
        kanjis.append(kanji)

# kanjis appearing as part of a word in jdict
jwords = np.array(list(jdict.keys()))
prob_entries = {}
kanji2word = {}
for wd in jwords:
    ks, rads, hir, kat = f_krhk(wd)
    for kanji in np.unique(ks):
        if kanji not in tdict.keys():
            prob_entries[kanji] = wd
        else:
            if kanji not in kanji2word.keys():
                kanji2word[kanji] = []
            kanji2word[kanji].append(wd)
# problems are a surname Tanpu and 0 symbol

# kanjis to decomposition

errs = {}
char_data = {}
for kanji in kanjis:
    entry = json.loads(tdict[kanji])
    if "head_templates" in entry.keys():
        if len(entry["head_templates"]) > 1:
            errs[kanji] = "multi_head_templates"
        char_data[kanji] = entry["head_templates"][0]["expansion"]
    else:
        if len(entry["senses"]) > 1:
            # check if all composition data in glosses are the same
            all_glosses = []
            for ind in range(len(entry["senses"])):
                if "glosses" in entry["senses"][ind].keys():
                    all_glosses.extend(entry["senses"][ind]["glosses"])
            comp_glosses = [gloss for gloss in all_glosses if "composition" in gloss]
            comps = ["composition" + gloss.split("composition")[1].split(")")[0] for gloss in comp_glosses]
            if len(np.unique(comps)) == 1:
                char_data[kanji] = comp_glosses[0]
            else:
                print(kanji)
                print(comps)
                char_data[kanji] = "|||".join(comp_glosses)
        else:
            if "glosses" in entry["senses"][0].keys():
                if len(entry["senses"][0]["glosses"]) > 1:
                    errs[kanji] = "multi_glosses"
                else:
                    char_data[kanji] = entry["senses"][0]["glosses"][0]
            else:
                errs[kanji] = "no_gloss"
## error is a character that redirects and has tag 'no-gloss'

comp_data = {}
for kanji, gloss in char_data.items():
    comp = ""
    if "|||" in gloss:
        glosses = gloss.split("|||")
    else:
        glosses = [gloss]
    for gl in glosses:
        if "composition" in gl:
            cp = gl.split("composition")[1]
            if "(" in cp:
                cp = cp.split("(")[0]
            if ")" in cp:
                cp = cp.split(")")[0]
            if len(comp) > 0:
                comp += " or "
            comp += cp
        else:
            print(kanji, end=",")
    comp_data[kanji] = comp
