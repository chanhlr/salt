# -*- coding: utf-8 -*-

# Import python libs
import os
import tempfile
import urllib2
import logging

# Import Salt Testing libs
from salttesting import TestCase, skipIf
from salttesting.helpers import (
    ensure_in_syspath,
    requires_network,
)

ensure_in_syspath('../../')
import integration
import shutil

# Import Salt libs
import salt.utils
from salt.modules import zcbuildout as buildout
from salt.modules import cmdmod as cmd

ROOT = os.path.join(integration.FILES, 'file', 'base', 'buildout')

buildout.__salt__ = {
    'cmd.run_all': cmd.run_all,
    'cmd.run': cmd.run,
    'cmd.retcode': cmd.retcode,
}

BOOT_INIT = {
    1: [
        'var/ver/1/bootstrap/bootstrap.py',
    ],
    2: [
        'var/ver/2/bootstrap/bootstrap.py',
        'b/bootstrap.py',
    ]}

log = logging.getLogger(__name__)


def download_to(url, dest):
    with salt.utils.fopen(dest, 'w') as fic:
        fic.write(
            urllib2.urlopen(url, timeout=10).read()
        )


class Base(TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.path.isdir(integration.TMP):
            os.makedirs(integration.TMP)
        cls.rdir = tempfile.mkdtemp(dir=integration.TMP)
        cls.tdir = os.path.join(cls.rdir, 'test')
        for idx, url in buildout._URL_VERSIONS.iteritems():
            log.debug('Downloading bootstrap from {0}'.format(url))
            dest = os.path.join(
                cls.rdir, '{0}_bootstrap.py'.format(idx)
            )
            try:
                download_to(url, dest)
            except urllib2.URLError:
                log.debug('Failed to download {0}'.format(url))

    @classmethod
    def tearDownClass(cls):
        if os.path.isdir(cls.rdir):
            shutil.rmtree(cls.rdir)

    def setUp(self):
        super(Base, self).setUp()
        self._remove_dir()
        shutil.copytree(ROOT, self.tdir)

        for idx in BOOT_INIT:
            path = os.path.join(
                self.rdir, '{0}_bootstrap.py'.format(idx)
            )
            for fname in BOOT_INIT[idx]:
                shutil.copy2(path, os.path.join(self.tdir, fname))

    def tearDown(self):
        super(Base, self).tearDown()
        self._remove_dir()

    def _remove_dir(self):
        if os.path.isdir(self.tdir):
            shutil.rmtree(self.tdir)


class BuildoutTestCase(Base):

    @requires_network()
    def test_onlyif_unless(self):
        b_dir = os.path.join(self.tdir, 'b')
        ret = buildout.buildout(b_dir, onlyif='/bin/false')
        self.assertTrue(ret['comment'] == 'onlyif execution failed')
        self.assertTrue(ret['status'] is True)
        ret = buildout.buildout(b_dir, unless='/bin/true')
        self.assertTrue(ret['comment'] == 'unless execution succeeded')
        self.assertTrue(ret['status'] is True)

    @requires_network()
    def test_salt_callback(self):
        @buildout._salt_callback
        def callback1(a, b=1):
            for i in buildout.LOG.levels:
                getattr(buildout.LOG, i)('{0}bar'.format(i[0]))
            return 'foo'

        def callback2(a, b=1):
            raise Exception('foo')

        ret1 = callback1(1, b=3)
        self.assertEqual(ret1['status'], True)
        self.assertEqual(ret1['logs_by_level']['warn'], ['wbar'])
        self.assertEqual(ret1['comment'], '')
        self.assertTrue(
            u''
            u'OUTPUT:\n'
            u'foo\n'
            u''
            in ret1['outlog']
        )

        self.assertTrue(u'Log summary:\n' in ret1['outlog'])
        self.assertTrue(
            u'\n'
            u'INFO: ibar\n'
            u'\n'
            u'WARN: wbar\n'
            u'\n'
            u'DEBUG: dbar\n'
            u'\n'
            u'ERROR: ebar\n'
            in ret1['outlog']
        )
        self.assertTrue('by level' in ret1['outlog_by_level'])
        self.assertEqual(ret1['out'], 'foo')
        ret2 = buildout._salt_callback(callback2)(2, b=6)
        self.assertEqual(ret2['status'], False)
        self.assertTrue(
            ret2['logs_by_level']['error'][0].startswith('Traceback'))
        self.assertTrue(
            'We did not get any '
            'expectable answer '
            'from buildout' in ret2['comment'])
        self.assertEqual(ret2['out'], None)
        for l in buildout.LOG.levels:
            self.assertTrue(0 == len(buildout.LOG.by_level[l]))

    @requires_network()
    def test_get_bootstrap_url(self):
        for path in [os.path.join(self.tdir, 'var/ver/1/dumppicked'),
                     os.path.join(self.tdir, 'var/ver/1/bootstrap'),
                     os.path.join(self.tdir, 'var/ver/1/versions')]:
            self.assertEqual(buildout._URL_VERSIONS[1],
                             buildout._get_bootstrap_url(path),
                             "b1 url for {0}".format(path))
        for path in [
            os.path.join(self.tdir, '/non/existing'),
            os.path.join(self.tdir, 'var/ver/2/versions'),
            os.path.join(self.tdir, 'var/ver/2/bootstrap'),
            os.path.join(self.tdir, 'var/ver/2/default'),
        ]:
            self.assertEqual(buildout._URL_VERSIONS[2],
                             buildout._get_bootstrap_url(path),
                             "b2 url for {0}".format(path))

    @requires_network()
    def test_get_buildout_ver(self):
        for path in [os.path.join(self.tdir, 'var/ver/1/dumppicked'),
                     os.path.join(self.tdir, 'var/ver/1/bootstrap'),
                     os.path.join(self.tdir, 'var/ver/1/versions')]:
            self.assertEqual(1,
                             buildout._get_buildout_ver(path),
                             "1 for {0}".format(path))
        for path in [os.path.join(self.tdir, '/non/existing'),
                     os.path.join(self.tdir, 'var/ver/2/versions'),
                     os.path.join(self.tdir, 'var/ver/2/bootstrap'),
                     os.path.join(self.tdir, 'var/ver/2/default')]:
            self.assertEqual(2,
                             buildout._get_buildout_ver(path),
                             "2 for {0}".format(path))

    @requires_network()
    def test_get_bootstrap_content(self):
        self.assertEqual(
            '',
            buildout._get_bootstrap_content(
                os.path.join(self.tdir, '/non/existing'))
        )
        self.assertEqual(
            '',
            buildout._get_bootstrap_content(
                os.path.join(self.tdir, 'var/tb/1')))
        self.assertEqual(
            'foo\n',
            buildout._get_bootstrap_content(
                os.path.join(self.tdir, 'var/tb/2')))

    @requires_network()
    def test_logger_clean(self):
        buildout.LOG.clear()
        # nothing in there
        self.assertTrue(
            True not in
            [len(buildout.LOG.by_level[a]) > 0
             for a in buildout.LOG.by_level])
        buildout.LOG.info('foo')
        self.assertTrue(
            True in
            [len(buildout.LOG.by_level[a]) > 0
             for a in buildout.LOG.by_level])
        buildout.LOG.clear()
        self.assertTrue(
            True not in
            [len(buildout.LOG.by_level[a]) > 0
             for a in buildout.LOG.by_level])

    @requires_network()
    def test_logger_loggers(self):
        buildout.LOG.clear()
        # nothing in there
        for i in buildout.LOG.levels:
            getattr(buildout.LOG, i)('foo')
            getattr(buildout.LOG, i)('bar')
            getattr(buildout.LOG, i)('moo')
            self.assertTrue(len(buildout.LOG.by_level[i]) == 3)
            self.assertEqual(buildout.LOG.by_level[i][0], 'foo')
            self.assertEqual(buildout.LOG.by_level[i][-1], 'moo')

    @requires_network()
    def test__find_cfgs(self):
        result = sorted(
            [a.replace(ROOT, '') for a in buildout._find_cfgs(ROOT)])
        assertlist = sorted(
            ['/buildout.cfg',
             '/c/buildout.cfg',
             '/etc/buildout.cfg',
             '/e/buildout.cfg',
             '/b/buildout.cfg',
             '/b/bdistribute/buildout.cfg',
             '/b/b2/buildout.cfg',
             '/foo/buildout.cfg'])
        self.assertEqual(result, assertlist)

    @requires_network()
    def test_upgrade_bootstrap(self):
        b_dir = os.path.join(self.tdir, 'b')
        bpy = os.path.join(b_dir, 'bootstrap.py')
        buildout.upgrade_bootstrap(b_dir)
        time1 = os.stat(bpy).st_mtime
        with salt.utils.fopen(bpy) as fic:
            data = fic.read()
        self.assertTrue('setdefaulttimeout(2)' in data)
        flag = os.path.join(b_dir, '.buildout', '2.updated_bootstrap')
        self.assertTrue(os.path.exists(flag))
        buildout.upgrade_bootstrap(b_dir, buildout_ver=1)
        time2 = os.stat(bpy).st_mtime
        with salt.utils.fopen(bpy) as fic:
            data = fic.read()
        self.assertTrue('setdefaulttimeout(2)' in data)
        flag = os.path.join(b_dir, '.buildout', '1.updated_bootstrap')
        self.assertTrue(os.path.exists(flag))
        buildout.upgrade_bootstrap(b_dir, buildout_ver=1)
        time3 = os.stat(bpy).st_mtime
        self.assertNotEqual(time2, time1)
        self.assertEqual(time2, time3)


@skipIf(salt.utils.which('virtualenv') is None,
        'The \'virtualenv\' packaged needs to be installed')
class BuildoutOnlineTestCase(Base):

    @classmethod
    def setUpClass(cls):
        super(BuildoutOnlineTestCase, cls).setUpClass()
        cls.ppy_dis = os.path.join(cls.rdir, 'pdistibute')
        cls.ppy_st = os.path.join(cls.rdir, 'psetuptools')
        cls.ppy_blank = os.path.join(cls.rdir, 'pblank')
        cls.py_dis = os.path.join(cls.ppy_dis, 'bin', 'python')
        cls.py_st = os.path.join(cls.ppy_st, 'bin', 'python')
        cls.py_blank = os.path.join(cls.ppy_blank, 'bin', 'python')
        # creating a new setuptools install
        ret1 = buildout._Popen((
            'virtualenv --no-site-packages {0};'
            '{0}/bin/pip install -U setuptools; '
            '{0}/bin/easy_install -U distribute;'
        ).format(cls.ppy_st))
        assert ret1['retcode'] == 0

        # creating a distribute based install
        try:
            ret20 = buildout._Popen((
                'virtualenv --no-site-packages --no-setuptools --no-pip {0}'
                ''.format(cls.ppy_dis)))
        except buildout._BuildoutError:
            ret20 = buildout._Popen((
                'virtualenv --no-site-packages {0}'.format(cls.ppy_dis))
            )
        assert ret20['retcode'] == 0

        download_to('https://pypi.python.org/packages/source'
                    '/d/distribute/distribute-0.6.43.tar.gz',
                    os.path.join(cls.ppy_dis, 'distribute-0.6.43.tar.gz'))

        ret2 = buildout._Popen((
            'cd {0} &&'
            ' tar xzvf distribute-0.6.43.tar.gz && cd distribute-0.6.43 &&'
            ' {0}/bin/python setup.py install'
        ).format(cls.ppy_dis))
        assert ret2['retcode'] == 0

        # creating a blank based install
        try:
            ret3 = buildout._Popen((
                'virtualenv --no-site-packages --no-setuptools --no-pip {0}'
                ''.format(cls.ppy_blank)))
        except buildout._BuildoutError:
            ret3 = buildout._Popen((
                'virtualenv --no-site-packages {0}'.format(cls.ppy_blank)))

        assert ret3['retcode'] == 0

    @requires_network()
    def test_buildout_bootstrap(self):
        b_dir = os.path.join(self.tdir, 'b')
        bd_dir = os.path.join(self.tdir, 'b', 'bdistribute')
        b2_dir = os.path.join(self.tdir, 'b', 'b2')
        self.assertTrue(buildout._has_old_distribute(self.py_dis))
        # this is too hard to check as on debian & other where old
        # packages are present (virtualenv), we cant have
        # a clean site-packages
        # self.assertFalse(buildout._has_old_distribute(self.py_blank))
        self.assertFalse(buildout._has_old_distribute(self.py_st))
        self.assertFalse(buildout._has_setuptools7(self.py_dis))
        self.assertTrue(buildout._has_setuptools7(self.py_st))
        self.assertFalse(buildout._has_setuptools7(self.py_blank))

        ret = buildout.bootstrap(
            bd_dir, buildout_ver=1, python=self.py_dis)
        comment = ret['outlog']
        self.assertTrue('--distribute' in comment)
        self.assertTrue('Generated script' in comment)

        ret = buildout.bootstrap(b_dir, buildout_ver=1, python=self.py_blank)
        comment = ret['outlog']
        # as we may have old packages, this test the two
        # behaviors (failure with old setuptools/distribute)
        self.assertTrue(
            ('Got ' in comment
             and 'Generated script' in comment)
            or ('setuptools>=0.7' in comment)
        )

        ret = buildout.bootstrap(b_dir, buildout_ver=2, python=self.py_blank)
        comment = ret['outlog']
        self.assertTrue(
            ('setuptools' in comment
             and 'Generated script' in comment)
            or ('setuptools>=0.7' in comment)
        )

        ret = buildout.bootstrap(b_dir, buildout_ver=2, python=self.py_st)
        comment = ret['outlog']
        self.assertTrue(
            ('setuptools' in comment
             and 'Generated script' in comment)
            or ('setuptools>=0.7' in comment)
        )

        ret = buildout.bootstrap(b2_dir, buildout_ver=2, python=self.py_st)
        comment = ret['outlog']
        self.assertTrue(
            ('setuptools' in comment
             and 'Creating directory' in comment)
            or ('setuptools>=0.7' in comment)
        )

    @requires_network()
    def test_run_buildout(self):
        b_dir = os.path.join(self.tdir, 'b')
        ret = buildout.bootstrap(b_dir, buildout_ver=2, python=self.py_st)
        self.assertTrue(ret['status'])
        ret = buildout.run_buildout(b_dir,
                                    parts=['a', 'b'], python=self.py_st)
        out = ret['out']
        self.assertTrue('Installing a' in out)
        self.assertTrue('Installing b' in out)

    @requires_network()
    def test_buildout(self):
        b_dir = os.path.join(self.tdir, 'b')
        ret = buildout.buildout(b_dir, buildout_ver=2, python=self.py_st)
        self.assertTrue(ret['status'])
        out = ret['out']
        comment = ret['comment']
        self.assertTrue(ret['status'])
        self.assertTrue('Creating directory' in out)
        self.assertTrue('Installing a.' in out)
        self.assertTrue('psetuptools/bin/python bootstrap.py' in comment)
        self.assertTrue('buildout -c buildout.cfg' in comment)
        ret = buildout.buildout(b_dir,
                                parts=['a', 'b', 'c'],
                                buildout_ver=2,
                                python=self.py_st)
        outlog = ret['outlog']
        out = ret['out']
        comment = ret['comment']
        self.assertTrue('Installing single part: a' in outlog)
        self.assertTrue('buildout -c buildout.cfg -N install a' in comment)
        self.assertTrue('Installing b.' in out)
        self.assertTrue('Installing c.' in out)
        ret = buildout.buildout(b_dir,
                                parts=['a', 'b', 'c'],
                                buildout_ver=2,
                                newest=True,
                                python=self.py_st)
        outlog = ret['outlog']
        out = ret['out']
        comment = ret['comment']
        self.assertTrue('buildout -c buildout.cfg -n install a' in comment)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(
        BuildoutTestCase,
        BuildoutOnlineTestCase,
        needs_daemon=False)
