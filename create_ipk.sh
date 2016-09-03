#!/bin/bash
# script taken from openwebif project
set -e

D=$(pushd $(dirname $0) &> /dev/null; pwd; popd &> /dev/null)
S=${D}/ipkg.src.$$
P=${D}/ipkg.tmp.$$
B=${D}/ipkg.build.$$
pushd ${D} &> /dev/null

PVER="0.61"
GITVER=$(git log -1 --format="%ci" | awk -F" " '{ print $1 }' | tr -d "-")
#DSTAGE="beta"
#DSTAGEVER="6"
VER=$PVER-$GITVER

PKG=${D}/enigma2-plugin-extensions-mediaplayer2_${VER}_all
PLUGINPATH=/usr/lib/enigma2/python/Plugins/Extensions/MediaPlayer2
popd &> /dev/null

rm -rf ${D}/ipkg.src*
rm -rf ${D}/ipkg.tmp*
rm -rf ${D}/ipkg.build*

mkdir -p ${P}
mkdir -p ${P}/CONTROL
mkdir -p ${B}
mkdir -p ${S}
git archive --format=tar HEAD | (cd ${S} && tar xf -)

cat > ${P}/CONTROL/control << EOF
Package: enigma2-plugin-extensions-mediaplayer2
Version: ${VER}
Architecture: all
Section: extra
Priority: optional
Maintainer: mxfitsat@gmail.com
Depends: enigma2-plugin-extensions-subssupport (>=1.5.1)
Recommends: python-sqlite3
Homepage: https://code.google.com/p/mediaplayer2-for-sh4/
Description: MediaPlayer with external subtitle support  $VER"
EOF

cat > ${P}/CONTROL/postrm << EOF
#!/bin/sh
rm -r /usr/lib/enigma2/python/Plugins/Extensions/MediaPlayer2 2> /dev/null
exit 0
EOF


chmod 755 ${P}/CONTROL/postrm

mkdir -p ${P}${PLUGINPATH}
cp -rp ${S}/plugin/* ${P}${PLUGINPATH}

msgfmt ${P}${PLUGINPATH}/locale/cs/LC_MESSAGES/MediaPlayer2.po -o ${P}${PLUGINPATH}/locale/cs/LC_MESSAGES/MediaPlayer2.mo
msgfmt ${P}${PLUGINPATH}/locale/sk/LC_MESSAGES/MediaPlayer2.po -o ${P}${PLUGINPATH}/locale/sk/LC_MESSAGES/MediaPlayer2.mo
msgfmt ${P}${PLUGINPATH}/locale/pl/LC_MESSAGES/MediaPlayer2.po -o ${P}${PLUGINPATH}/locale/pl/LC_MESSAGES/MediaPlayer2.mo

#echo "compiling to optimized python bytecode"
#python -O -m compileall ${P} 1> /dev/null

#find ${P} -name "*.po" -exec rm {} \;
find ${P} -name "*.pyo" -print -exec rm {} \;
find ${P} -name "*.pyc" -print -exec rm {} \;

mkdir -p ${P}/tmp/mediaplayer2
mkdir -p ${P}/tmp/mediaplayer2/python2.6/
mkdir -p ${P}/tmp/mediaplayer2/python2.7/

tar -C ${P} -czf ${B}/data.tar.gz . --exclude=CONTROL
tar -C ${P}/CONTROL -czf ${B}/control.tar.gz .

echo "2.0" > ${B}/debian-binary

cd ${B}
ls -la
ar -r ${PKG}.ipk ./debian-binary ./control.tar.gz ./data.tar.gz
ar -r ${PKG}.deb ./debian-binary ./control.tar.gz ./data.tar.gz
cd ${D}

rm -rf ${P}
rm -rf ${B}
rm -rf ${S}

