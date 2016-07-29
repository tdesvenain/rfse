# -*- coding: utf-8 -*-

import sys
import optparse
import transaction
from zope.site.hooks import setSite
from ZODB.POSException import ConflictError
from Products.CMFEditions.utilities import dereference

from AccessControl.SecurityManagement import newSecurityManager
from AccessControl.SecurityManager import setSecurityPolicy
from Testing.makerequest import makerequest
from Products.CMFCore.tests.base.security import OmnipotentUser
from Products.CMFCore.tests.base.security import PermissiveSecurityPolicy
from Products.Archetypes.utils import shasattr

version = '0.2.1'
usage = "Usage: /your/instance run clean_history.py [options] [sites]"
description = (
    "Cleanup CMFEdition history in Plone sites. "
    "Default is: all sites in the database.")
p = optparse.OptionParser(
    usage=usage,
    version="%prog " + version,
    description=description,
    prog="clean_history")
p.add_option(
    '--portal-type', '-p',
    dest="portal_types",
    default=[],
    action="append",
    metavar="PORTAL_TYPE",
    help=("Select to cleanup only histories for a kind of portal_type. "
          "Default is all types. Can be called multiple times."))
p.add_option(
    '--keep-history', '-k',
    type="int",
    dest="keep_history",
    default=None,
    metavar="HISTORY_SIZE",
    help=('Before purging, temporary set the value of '
          '"maximum number of versions to keep in the storage" to this '
          'value in the portal_purgehistory. Default is: do not change '
          'the value. In any case, the original value will be restored, '
          'except when you use the --permanent option. '
          'The minimum is 1: the original object is included '
          'in the count.'))
p.add_option(
    '--permanent',
    action="store_true",
    dest="permanent",
    metavar="PERMANENT",
    help=('Set the "maximum number of versions to keep in the storage" in '
          'the portal_purgehistory permanently to the --keep-history value. '
          'Default is False: restore the original value. '
          'This option is useful when you want to change the stored value '
          'and purge all too old versions at the same time, '
          'especially when the value was unlimited (-1) until now.'))
p.add_option(
    '--dry-run',
    action="store_true",
    dest="dry_run",
    metavar="DRY_RUN",
    help='Dry run: do not commit any changes.')
p.add_option(
    '--verbose',
    '-v',
    action="store_true",
    default=False,
    help="Show verbose output, for every cleaned content's history.")

args = sys.argv[1:]
# In Plone 4 and higher, the arguments we really want are prepended
# with '-c' and '..../clean_history.py'.  Or possibly this depends on
# the version of the plone.recipe.zope2instance recipe or the Zope
# version.  So we strip this.
if len(args) >= 2 and args[0] == '-c' and args[1].endswith('.py'):
    args = args[2:]
options, psite = p.parse_args(args)
pp_type = options.portal_types

try:
    foo = app
except NameError:
    print p.print_help()
    sys.exit(1)

if options.keep_history is not None and options.keep_history < 1:
    print('Error: the keep history argument must be 1 or higher: '
          'the original object is included in the count.')
    sys.exit(1)


def commit(note):
    """Commit transaction, with note.
    """
    print(note)
    if options.dry_run:
        print('Dry run selected, not committing.')
        return
    # Commit transaction and add note.
    tr = transaction.get()
    tr.note(note)
    transaction.commit()


def spoofRequest(app):
    """
    Make REQUEST variable to be available on the Zope application server.

    This allows acquisition to work properly
    """
    _policy = PermissiveSecurityPolicy()
    setSecurityPolicy(_policy)
    newSecurityManager(None, OmnipotentUser().__of__(app.acl_users))
    return makerequest(app)

# Enable Faux HTTP request object
app = spoofRequest(app)  # noqa

sites = [(id, site) for (id, site) in app.items() if hasattr(
    site, 'meta_type') and site.meta_type == 'Plone Site']

print 'Starting analysis for %s. Types to cleanup: %s' % (
    not psite and 'all sites' or ', '.join(psite),
    not pp_type and 'all' or ', '.join(pp_type))

for id, site in sites:
    if not psite or id in psite:
        print "Analyzing %s" % id
        setSite(site)
        policy = site.portal_purgepolicy
        portal_repository = site.portal_repository
        if (policy.maxNumberOfVersionsToKeep == -1 and
                options.keep_history is None):
            print("... maxNumberOfVersionsToKeep is -1 and no --keep-history "
                  "argument has been given; skipping")
            continue

        old_maxNumberOfVersionsToKeep = policy.maxNumberOfVersionsToKeep
        if options.keep_history is not None:
            print "... Putting maxNumberOfVersionsToKeep from %d to %s" % (
                old_maxNumberOfVersionsToKeep, options.keep_history)
            if options.permanent:
                print "This change is permanent."
            else:
                print "This change is temporary."
            policy.maxNumberOfVersionsToKeep = options.keep_history
            keep = options.keep_history
        else:
            keep = policy.maxNumberOfVersionsToKeep

        # Search without restrictions, like language.
        search = site.portal_catalog.unrestrictedSearchResults
        if pp_type:
            results = search(portal_type=pp_type)
        else:
            results = search()
        for x in results:
            if options.verbose:
                print "... cleaning history for %s (%s)" % (
                    x.getPath(), x.portal_type)
            try:
                obj = x._unrestrictedGetObject()
                isVersionable = portal_repository.isVersionable(obj)
                if isVersionable:
                    obj, history_id = dereference(obj)
                    policy.beforeSaveHook(history_id, obj)
                    if shasattr(obj, 'version_id') and keep <= 1:
                        del obj.version_id
                    if options.verbose:
                        print "... cleaned!"
            except (ConflictError, KeyboardInterrupt):
               raise
            except Exception, inst:
                # sometimes, even with the spoofed request, the getObject
                # failed
                print "ERROR purging %s (%s)" % (x.getPath(), x.portal_type)
                print "    %s" % inst

        if not options.permanent:
            policy.maxNumberOfVersionsToKeep = old_maxNumberOfVersionsToKeep

        uidcatalog = site.uid_catalog
        hstore = site.portal_historiesstorage
        shadowStore = hstore._getShadowStorage(autoAdd=False)

        historyIds = shadowStore._storage
        repo = hstore.zvc_repo

        for historyId in list(historyIds.keys()):
            history = hstore._getShadowHistory(historyId)
            zv_hist_id = history._full[0]['vc_info'].history_id
            not_found = False
            if zv_hist_id in repo._histories:
                zv_history = repo._histories[zv_hist_id]
                version = zv_history._versions[zv_history._versions.keys()[0]]

                if not hasattr(version._data._object, 'object'):
                    continue

                obj = version._data._object.object.aq_base
                try:
                    uid = obj.UID()
                except TypeError:
                    not_found = True
                else:
                    brains = uidcatalog.searchResults(UID=uid)
                    if len(brains) == 0:
                        not_found = True

            if not_found:
                print 'deleting', str(historyId), zv_hist_id
                del historyIds[historyId]
                try:
                    del repo._histories[zv_hist_id]
                except KeyError:
                    pass

        commit('Purged CMFEditions history to %d versions.' % keep)

print 'End analysis'
sys.exit(0)
