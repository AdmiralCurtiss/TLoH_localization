import xml.etree.cElementTree as ET
import re
from base64 import b64encode, b64decode
from collections import OrderedDict

TBL_SIGNATURE_LEN = 2
HEADER_TAG = "header"
ENTRY_TAG = "Entry"
GROUP_TAG = "Group"

common_entry_ptrns = ["[\xe0-\xef].?.?", ".?\x01", "%[ds]", "#[0-9]*C", "#[0-9a-f]*"]
common_entry_ptrn = "(%s)" % ("|".join(common_entry_ptrns))

_match = lambda s, ptrns: any([re.match(i, s) for i in ptrns])

def u_test(s, enc = "shift_jis"):
	"""Try converting string to unicode. 
	If that fails, will return base64-encoded string instead."""
	b64_encoded = False

	try:
		res = s.decode(enc) 
	except:
		b64_encoded = True
		res = b64encode(s)
		
	return res, b64_encoded
	
def _get_tbl_tag(in_file, is_tbl_file, tbl_tag_max_len = 200):
	if is_tbl_file:
		s = open(in_file, "rb").read(tbl_tag_max_len)
		return s[TBL_SIGNATURE_LEN : s.find("\x00", TBL_SIGNATURE_LEN)]
	else:
		root = ET.parse(in_file).getroot()
		doc = root.find("doc")
		el_header = doc.find(HEADER_TAG)
		return el_header.get("type")

def read_tbl(in_file, l_tbl_tags):
	"""Read binary *.tbl file.
	Returns *.tbl header and list of OrderedDict's representing each text or binary data entry."""

	def _split(s):
		text_start = s[:-1].rfind("\x00") + 1
		data = s[:text_start]
		text = s[text_start : -1]
		return data, text

	res = []
	data = open(in_file, "rb").read()
	ptrn = "(%s)" % "|".join(l_tbl_tags)
	raw_strings = re.split(ptrn, data)

	header = OrderedDict()
	header["data"] = b64encode(raw_strings[0])

	tag_type = ""
	for raw_string in raw_strings[1:]:
		entry_group = OrderedDict()
		# If raw_string doesn't match with any tag, 
		# just proceed it as an entry text. Otherwise,
		# remember a tag type and proceed the next raw_string.
		if not raw_string in l_tbl_tags:
			data, raw_text = _split(raw_string)
		else:
			tag_type = raw_string
			continue
	
		entry_group["data"] = b64encode(data)
		entry_group["entries"] = []
		assert(tag_type)
		entry_group["type"] = tag_type
		tag_type = ""

		for entry_text in re.split(common_entry_ptrn, raw_text):
			if not entry_text:
				continue

			entry = OrderedDict()

			if not _match(entry_text, common_entry_ptrns):
				entry_text, b64 = u_test(entry_text)
				entry["text"] = entry_text
				if b64:
					entry["b64_encoded"] = b64
			else:
				entry["data"] = b64encode(entry_text)

			entry_group["entries"].append(entry)


		res.append(entry_group)

	return header, res
	
def _indent(elem, level = 0):
	i = "\n" + level * "  "
	if len(elem):
		if not elem.text or not elem.text.strip():
			elem.text = i + "  "
		if not elem.tail or not elem.tail.strip():
			elem.tail = i
		for elem in elem:
			_indent(elem, level + 1)
		if not elem.tail or not elem.tail.strip():
			elem.tail = i
	else:
		if level and (not elem.tail or not elem.tail.strip()):
			elem.tail = i

def write_xml(out_file, header, l_groups):
	"""Write *.tbl file data to XML file.
	Params:
	@header - *.tbl file header
	@l_groups - list of OrderedDict's representing each text or binary data entry."""

	root = ET.Element("root")
	doc = ET.SubElement(root, "doc")
	ET.SubElement(doc, HEADER_TAG).text = header["data"]
	
	idx = 0
	for l_group in l_groups:
		el_group = ET.SubElement(doc, GROUP_TAG, type = l_group["type"], data = l_group["data"], idx = "%d" % idx)	
		for l_entry in l_group["entries"]:
			if "data" in l_entry:
				ET.SubElement(el_group, ENTRY_TAG, data = l_entry["data"]).text = ""
			elif "text" in l_entry:
				if "b64_encoded" in l_entry and l_entry["b64_encoded"]:
					ET.SubElement(el_group, ENTRY_TAG, b64_encoded = "%s" %\
					        l_entry["b64_encoded"]).text = l_entry["text"]
				else:
					ET.SubElement(el_group, ENTRY_TAG).text = l_entry["text"]
		
		idx += 1
		
	_indent(root)
	open(out_file, "wb").write(ET.tostring(root, encoding='utf8', method='xml'))
	
def read_xml(in_file):
	"""Read XML file containing parsed *.tbl file data.
	Returns *.tbl header and list of OrderedDict's representing each text or binary data entry."""

	res = []
	root = ET.parse(in_file).getroot()
	doc = root.find("doc")
	el_header = doc.find(HEADER_TAG)	
	el_groups = doc.findall(GROUP_TAG)
	for el_group in el_groups:
		entry_group = OrderedDict()
		entry_group["entries"] = []
		entry_group["data"] = el_group.get("data")
		entry_group["type"] = el_group.get("type")
		el_entries = el_group.findall(ENTRY_TAG)
		for el_entry in el_entries:
			entry = OrderedDict()
			data = el_entry.get("data")
			text = el_entry.text
			if data:
				entry["data"] = data
			elif text:
				entry["text"] = text
				b64 = el_entry.get("b64_encoded")
				if b64:
					entry["b64_encoded"] = eval(b64)
			entry_group["entries"].append(entry)
		res.append(entry_group)

	header = OrderedDict()
	header["data"] = el_header.text
	return header, res
	
def write_tbl(out_file, header, l_groups):
	"""Write *.tbl data to file.
	Params:
	@header - *.tbl file header
	@l_groups - list of OrderedDict's representing each text or binary data entry."""
	
	res = []
	res.append(b64decode(header["data"]))
	
	for l_group in l_groups:
		res.append(l_group["type"])
		res.append(b64decode(l_group["data"]))
		for l_entry in l_group["entries"]:
			if "data" in l_entry:
				res.append(b64decode(l_entry["data"]))
			elif "text" in l_entry:
				if l_entry.get("b64_encoded"):
					text = b64decode(l_entry["text"])
				else:
					text = l_entry["text"].encode("shift_jis")
				
				res.append(text)
		res.append("\x00")
	open(out_file, "wb").write(b"".join(res))
	
def dump_txt(out_file, l_groups):
	"""Dump text entries of *.tbl file"""
	
	res = []
	idx = 0
	for l_group in l_groups:
		res.append("%d)\n" % idx)
		for entry in l_group["entries"]:
			if not "text" in entry:
				continue
			res.append(entry["text"] + "\n")
		idx += 1
	return open(out_file, "wb")\
	       .write("".join(res).encode("u8"))