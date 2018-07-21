import sys
import json
from optparse import OptionParser

def ensure_list(x):
	if isinstance(x, list):
		return x
	return [x]

optparser = OptionParser(usage="usage: %prog [options] ")
optparser.add_option("-x", "--oxm_file", dest="oxm",
	default="aai_oxm_v1.json", help="oxm file")
optparser.add_option("-e", "--edge_rules_file", dest="erules",
	default="DbEdgeRules_v1.json", help="edge rules file")
optparser.add_option("-E", "--no_edge_rules", dest="no_erules",
	default=False, action="store_true", help="don't add edges from edge rules")
optparser.add_option("-N", "--all_nodes", dest="all_nodes",
	default=False, action="store_true", help="don't discard dummy nodes")
optparser.add_option("-C", "--all_contains", dest="all_contains",
	default=False, action="store_true", help="don't discard dummy contains relationships")
optparser.add_option("-n", "--nodes", dest="src_nodes",
		 default="", help="restrict graph to these source nodes" )

(options, args) = optparser.parse_args()

# the oxm file
try:
	xfl = open(options.oxm,"r")
except IOError as e:
	sys.stderr.write("I/O Error ({0}): ({1}) opening {2}\n".format(e.errno, e.strerror, options.oxm))
	sys.exit(1)
except:
	sys.stderr.write("Unexpected error opening "+options.oxm+" : "+sys.exc_info()[0]+"\n")
	sys.exit(1)

xdoc = json.load(xfl)
xfl.close()

# get relational edges from the edge rules file
try:
	efl = open(options.erules,"r")
except IOError as e:
	sys.stderr.write("I/O Error ({0}): ({1}) opening {2}\n".format(e.errno, e.strerror, options.erules))
	sys.exit(1)
except:
	sys.stderr.write("Unexpected error opening "+options.erules+" : "+sys.exc_info()[0]+"\n")
	sys.exit(1)

edoc = json.load(efl)
efl.close()



source_nodes = set()
node_set = set()
if options.src_nodes != "":
	source_nodes = set(options.src_nodes.split(","))
	node_set = set(options.src_nodes.split(","))


ns_prefix = xdoc["xml-bindings"]["@package-name"]
xnodes = xdoc["xml-bindings"]["java-types"]["java-type"]

# the processed nodes
nodes = {}
alias = {} # node alias ...?

# take a first pass to collect all nodes
pos = 0
for xn in xnodes:
	name = xn["@name"]
	alt_name = xn["xml-root-element"]["@name"]
	alias[alt_name] = name # refs might be to this
	nodes[name] = {"alias": alias, "fields": [], "contains": [], "dep_on": [],
	               "container": [], "keys": [], "dnm" : "n"+str(pos)}
	pos += 1

# compute the node_set now, even if its not used.
rule_list = edoc["rules"]
for e in rule_list:
	src = e["from"]
	if src in alias:
		src = alias[src]
	tgt = e["to"]
	if tgt in alias:
		tgt = alias[tgt]
	if src in source_nodes:
		node_set.add(tgt)
	if tgt in source_nodes:
		node_set.add(src)



for xn in xnodes:
	name = xn["@name"]
#	if name=="L3Network":
#		sys.stderr.write("Processing node "+name+"\n")
	if "java-attributes" in xn:

		unprocessed = []
		for k in xn["java-attributes"].keys():
			if k not in ["xml-element", "xml-any-element"]:
				unprocessed.append(k)
		if len(unprocessed)>0:
			sys.stderr.write("unknown elements in "+name+"[java-attributes]: "+", ".join(unprocessed)+"\n")

		if "xml-element" in xn["java-attributes"]:
			fields = ensure_list(xn["java-attributes"]["xml-element"])
			for fld in fields:
				fname = fld["@name"]
				typ = fld["@type"]
				is_real_field = True
				if typ.startswith(ns_prefix):
					typ = typ[len(ns_prefix)+1:]
					is_real_field = False
				if is_real_field:
					nodes[name]["fields"].append({"name": fname, "type": typ})
				else:
					if typ not in nodes:
						sys.stderr.write("Warning, node "+name+" has field "+fname+" which contains "+typ+", but there is no such node in the document.\n");
					else:
						multi = False
						if "@container-type" in fld:
							multi = True
						nodes[name]["contains"].append({"name": fname, "type": typ, "multi": multi})
				if "@xml-key" in fld and fld["@xml-key"].lower() == "true":
					nodes[name]["keys"].append(fname)
# TODO handle xml-any-element

# node properties.  There can be variant forms so collect all lists
		if "xml-properties" in xn:
#			if "xml-property" not in xn["xml-properties"]:
#				print "xml-property not in "+name+"[xml-properties]"
			xps = ensure_list(xn["xml-properties"])
			xplist = []
			for xp in xps:
				if isinstance(xp["xml-property"], dict):
					xplist.append(xp["xml-property"])
				if isinstance(xp["xml-property"], list):
					xplist.extend(xp["xml-property"])

			for xpl in xplist:
				if xpl["@name"] == "dependentOn":
					nodes[name]["dep_on"] = xpl["@value"].split(",")
				if xpl["@name"] == "container":
					nodes[name]["container"] = xpl["@value"].split(",")

elist = []
# any relationship to these are bogus
contains_blacklist = ["RelationshipList"]
if options.all_contains:
	contains_blacklist = []

# compute the node blacklist.
# HACK relying on plural naming convention
# HACK prelaod with unusual plural spellings
node_blacklist = {"Activities": "Activity", "Chassies": "Chassis", "Complexes": "Complex", "OwningEntities": "OwningEntity", "ExtraProperties": "ExtraProperty"}
for n in nodes:
	for c in nodes[n]["contains"]:
		ct = c["type"]
		if ct in nodes:
			cn = ct
		else:
			cn = alias[ct]
		if len(nodes[cn]["fields"]) == 0 and cn[-1]=="s" and cn[:-1] in nodes:
			node_blacklist[cn] = cn[:-1]

if options.all_nodes:
	node_blacklist = []

# depends-on and contains edges
for n in nodes:
#	print "processing "+n
	if n in node_blacklist:
		continue

	for c in nodes[n]["contains"]:
#		print "\t contains "+str(c)
		ct = c["type"]
		if ct in nodes:
			cn = ct
		else:
			cn = alias[ct]

		if cn in node_blacklist:
			cn = node_blacklist[cn]

		if cn not in contains_blacklist:
			payload = nodes[n]["dnm"]+" -> "+nodes[cn]["dnm"]+" [color=black, weight=8];"
		if len(source_nodes)==0 or (cn in source_nodes and n in source_nodes):
			elist.append(payload)

	for d in nodes[n]["dep_on"]:
		if d in nodes:
			dn = d
		else:
			dn = alias[d]
		payload = nodes[dn]["dnm"]+" -> "+nodes[n]["dnm"]+" [color=black, style=dotted];"
		if len(source_nodes)==0 or (dn in source_nodes and n in source_nodes):
			elist.append(payload)

# list nodes which are not blacklisted
nlist = []
for n in nodes:
	if n not in node_blacklist:
		label = n
		if len(nodes[n]["keys"])>0:
			label+="\n("+",".join(nodes[n]["keys"])+")"
		payload = nodes[n]["dnm"]+" [label=\""+label+"\""
		if len(nodes[n]["fields"])>0:
			payload += ", shape=ellipse];"
		else:
			payload += "style=filled, fillcolor=lightgrey, shape=box];"
		if len(source_nodes)==0 or n in node_set:
			nlist.append(payload)

# edge color management
colors = ["red", "blue", "green", "orange", "purple", "gold", "brown", "gray", "pink", "khaki", "darkorange", "yellowgreen", "seagreen", "cyan", "navy", "plum", "darkturquoise"]
cpos = 0
edge_colors = {}

rule_list=[]
if not options.no_erules:
	rule_list = edoc["rules"]
eno=0
for e in rule_list:
	src = e["from"]
	if src in alias:
		src = alias[src]
	tgt = e["to"]
	if tgt in alias:
		tgt = alias[tgt]
	label = e["label"]
	if label not in edge_colors:
		edge_colors[label] = colors[cpos]
		cpos+=1
		if cpos>=len(colors):
			cpos=0

	label_parts = label.split(".")
	short_label = label_parts[-1]

	if src in node_blacklist:
		sys.stderr.write("edge number "+str(eno)+" is "+src+"->"+tgt+", but "+src+" is not in the set of nodes.\n")
		continue
	if tgt in node_blacklist:
		sys.stderr.write("edge number "+str(eno)+" is "+src+"->"+tgt+", but "+tgt+" is not in the set of nodes.\n")
		continue

	payload = nodes[src]["dnm"]+" -> "+nodes[tgt]["dnm"]+" [label=\""+short_label+"\", color="+edge_colors[label]+"];"
	if len(source_nodes)==0 or (src in node_set and tgt in node_set):
		elist.append(payload)
	eno+=1



	
# dump the dot
print "digraph narad_model{"
print "\n".join(nlist)
print "\n".join(elist)
print "}"
	
	
					

	





