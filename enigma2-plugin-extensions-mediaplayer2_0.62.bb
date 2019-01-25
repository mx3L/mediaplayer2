SUMMARY = "MediaPlayer2 for Enigma2"
HOMEPAGE = "https://github.com/mx3L/mediaplayer2"
LICENSE = "GPL-2.0"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/GPL-2.0;md5=801f80980d171dd6425610833a22dbe6"

RDEPENDS_${PN} = "enigma2-plugin-extensions-subssupport"

SRCREV = "3a21a388e7326cba690666cec5324f8da35d50d8"
PV = "0.62"
PR = "r0"

SRC_URI = "git://github.com/mx3L/mediaplayer2;protocol=git;branch=master"

S = "${WORKDIR}/git"

do_compile () {
    cd ${S}/plugin/locale/
    for i in `ls -d */`
    do
        msgfmt -o $i/LC_MESSAGES/MediaPlayer2.mo $i/LC_MESSAGES/MediaPlayer2.po
    done
    cd ..
}

do_install () {
    mkdir -p ${D}/${libdir}/enigma2/python/Plugins/Extensions/MediaPlayer2
    cp -r ${S}/plugin/* ${D}/${libdir}/enigma2/python/Plugins/Extensions/MediaPlayer2/
}

pkg_postrm_${PN} () {
    rm -rf ${libdir}/enigma2/python/Plugins/Extensions/MediaPlayer2
}

FILES_${PN} = "${libdir}/enigma2/python/Plugins/Extensions/MediaPlayer2"

