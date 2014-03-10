#
# elastiq-setup.py -- by Dario Berzano <dario.berzano@cern.ch>
#
# Plugin for amiconfig for configuring elastiq.
#
# See: https://github.com/dberzano/elastiq
#

import time
import os, stat
import pwd, grp
import base64
import StringIO

from amiconfig.errors import *
from amiconfig.lib import util
from amiconfig.plugin import AMIPlugin

class AMIConfigPlugin(AMIPlugin):
    name = 'elastiq-setup'

    def configure(self):
        """
        elastiq features an ini configuration file with sections, keys and
        values:

        # elastiq configuration file

        [section1]
        key1 = value1

        [section2]
        key2 = value2
        key3 = value3
        ...

        This plugin produces the above file from a single corresponding section
        in amiconfig's user-data:

        [elastiq-setup]
        section1_key1=value1
        section2_key2=value2
        section2_key3=value3
        ...

        where the format of each key/value pair is:

        <section>_<key>=<value>

        Variables can be specified in any order, and they will be grouped in
        sections accordingly.
        """

        cfgfile = '/etc/elastiq.conf'
        worker_ud = '/var/lib/amiconfig/scalable.user-data'

        cfgraw = self.ud.getSection('elastiq-setup')

        # You can use this space for storing defaults like this:
        # cfgvar = {
        #     'elastiq': {
        #         'sleep_s': 5,
        #         'log_level': 20
        #     }
        # }
        # See https://github.com/dberzano/elastiq/blob/master/elastiq/etc/elastiq.conf.example for inspirationb
        cfgvar = {}

        for k,v in cfgraw.iteritems():
            if k[0:2] == '__':
                continue
            s = k.split('_', 1)
            if len(s) != 2:
                continue
            section = s[0]
            key = s[1]
            if not section in cfgvar:
                cfgvar[section] = { key: v }
            else:
                cfgvar[section][key] = v

        # Base64'd version of the user-data for workers ("scalable services")
        try:
            b64d = StringIO.StringIO()
            ud = open(worker_ud, 'r')
            base64.encode(ud, b64d)
            ud.close()
            if not 'elastiq' in cfgvar:
                cfgvar['elastiq'] = None
            cfgvar['elastiq']['user_data_b64'] = b64d.getvalue().replace('\n', '')
            b64d.close()

        except IOError as e:
            print 'Cannot open user-data of workers %s: %s' % (worker_ud, e)
            if 'elastiq' in cfgvar:
                cfgvar['elastiq'].pop('user_data_b64', None)

        #
        # Configuration file contains sensitive information: chown/chmod
        # before writing it
        #

        # Get uid/gid for elastiq/elastiq (they must exist)
        try:
            uid = pwd.getpwnam('elastiq').pw_uid
            gid = grp.getgrnam('elastiq').gr_gid
        except KeyError as e:
            print 'Cannot find elastiq user/group: %s' % elastiq
            return # cannot continue

        # Create empty file
        try:
            fout = open(cfgfile, 'w')
            fout.close()
        except IOError as e:
            print 'Cannot touch elastiq configuration %s: %s' % (cfgfile, e)
            return

        # Change owner and mode
        try:
            os.chown(cfgfile, uid, gid)
            # chmod 0660 --> contains sensitive info!
            os.chmod(cfgfile, stat.S_IRUSR|stat.S_IWUSR | stat.S_IRGRP|stat.S_IWGRP)
        except OSError as e:
            print 'Cannot chown/chmod %s: %s' % (cfgfile, e)
            return

        # Write configuration
        try:
            fout = open(cfgfile, 'w')
            fout.write('# Automatically generated by the elastiq-setup plugin of amiconfig\n')
            fout.write('# Generated at %s\n\n' % (time.strftime('%Y-%m-%d %H:%M:%S %z')))

            for s,c in cfgvar.iteritems():
                fout.write('[%s]\n' % s)
                for k,v in c.iteritems():
                    fout.write('%s = %s\n' % (k,v))
                fout.write('\n')

            fout.close()
        except IOError as e:
            print 'Cannot produce elastiq configuration %s: %s' % (cfgfile, e)

        # Activate service and start
        os.system('/sbin/chkconfig elastiq on')
        os.system('/sbin/service elastiq restart')
