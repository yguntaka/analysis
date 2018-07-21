import json
import xmltodict
import sys

try:
	dfl = open(sys.argv[1],"r")
except IOError as e:
	sys.stderr.write("I/O Error ({0}): ({1}) opening {2}\n".format(e.errno, 
e.strerror, datfl))
	sys.exit(1)
except:
	sys.stderr.write("Unexpected error opening "+sys.argv[1]+" : "+sys.exc_info()[
0]+"\n")

xdat = dfl.read()
dfl.close()

jdat = xmltodict.parse(xdat)
print json.dumps(jdat, indent=2)
