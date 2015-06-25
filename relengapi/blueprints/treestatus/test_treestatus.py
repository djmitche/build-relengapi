# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import datetime
import mock
import pprint

from contextlib import contextmanager
from flask import json
from nose.tools import eq_
from relengapi import p
from relengapi.blueprints.treestatus import model
from relengapi.lib import auth
from relengapi.lib.testing.context import TestContext


tree1_json = {
    'tree': 'tree1',
    'status': 'closed',
    'reason': 'because',
    'message_of_the_day': 'enjoy troy',
}


def db_setup(app):
    session = app.db.session('treestatus')
    tree = model.DbTree(
        tree=tree1_json['tree'],
        status=tree1_json['status'],
        reason=tree1_json['reason'],
        message_of_the_day=tree1_json['message_of_the_day'])
    session.add(tree)

    def when(day):
        return datetime.datetime(2015, 7, day, 17, 44, 00)
    for tree, action, when, reason, tags in [
        ('tree1', 'opened', when(13), 'i wanted to', ['a']),
        ('tree1', 'opened', when(15), 'i really wanted to', []),
        ('tree1', 'closed', when(14), 'because', ['a', 'b']),
        ('tree2', 'approval required', when(11), 'so there', []),
    ]:
        l = model.DbLog(
            tree=tree,
            when=when,
            who='dustin',
            action=action,
            reason=reason,
            tags=tags)
        session.add(l)
        when += datetime.timedelta(days=1)
    session.commit()


def db_setup_stack(app):
    for tn in range(3):
        session = app.db.session('treestatus')
        tree = model.DbTree(
            tree='tree%d' % tn,
            status='closed',
            reason=['bug 123', 'bug 456', 'bug 456'][tn],
            message_of_the_day='tree %d' % tn)
        session.add(tree)

    def ls(status, reason):
        return json.dumps({'status': status, 'reason': reason})

    # first change closed tree0 and tree1
    stack = model.DbStatusStack(
        who='dustin', reason='bug 123', status='closed',
        when=datetime.datetime(2015, 7, 14))
    session.add(stack)
    for tree in 'tree0', 'tree1':
        session.add(model.DbStatusStackTree(tree=tree, stack=stack,
                                            last_state=ls('open', tree)))

    # second change closed tree1 and tree2
    stack = model.DbStatusStack(
        who='dustin', reason='bug 456', status='closed',
        when=datetime.datetime(2015, 7, 16))
    session.add(stack)
    session.add(model.DbStatusStackTree(tree='tree1', stack=stack,
                                        last_state=ls('closed', 'bug 123')))
    session.add(model.DbStatusStackTree(tree='tree2', stack=stack,
                                        last_state=ls('open', 'tree2')))

    session.commit()


def userperms(perms, email='user@domain.com'):
    u = auth.HumanUser(email)
    u._permissions = set(perms)
    return u

admin_and_sheriff = userperms([p.treestatus.admin, p.treestatus.sheriff])
admin = userperms([p.treestatus.admin])
sheriff = userperms([p.treestatus.sheriff])

test_context = TestContext(databases=['treestatus'],
                           db_setup=db_setup)


@contextmanager
def set_time(now):
    with mock.patch('relengapi.lib.time.now') as fake_now:
        fake_now.return_value = now
        yield


def assert_logged(app, tree, action, reason, when=None,
                  who='human:user@domain.com', tags=[]):
    with app.app_context():
        session = app.db.session('treestatus')
        q = session.query(model.DbLog)
        q = q.filter_by(tree=tree)
        q = q.order_by(model.DbLog.when)
        logs = q[:]
        for l in logs:
            if l.action != action:
                continue
            if l.reason != reason:
                continue
            if when and l.when != when:
                continue
            if l.who != who:
                continue
            if l.tags != tags:
                continue
            return  # success!
        pprint.pprint([l.__dict__ for l in logs])
        raise AssertionError("no matching log")


@test_context
def test_index_view(client):
    """Getting /treestatus/ results in an index page"""
    resp = client.get('/treestatus/')
    assert 'TreeListController' in resp.data


@test_context
def test_tree_view(client):
    """Getting /treestatus/tree1 results in a tree detail page"""
    resp = client.get('/treestatus/details/tree1')
    assert 'TreeDetailController' in resp.data


@test_context
def test_get_trees(client):
    """Getting /treestatus/trees results in a dictionary of trees keyed by
    name"""
    resp = client.get('/treestatus/trees')
    eq_(json.loads(resp.data)['result'], {'tree1': tree1_json})


@test_context
def test_get_tree(client):
    """Getting /treestatus/trees/tree1 results in the tree data"""
    resp = client.get('/treestatus/trees/tree1')
    eq_(json.loads(resp.data)['result'], tree1_json)


@test_context
def test_get_tree_nosuch(client):
    """Getting /treestatus/trees/NOSUCH results in a 404"""
    resp = client.get('/treestatus/trees/NOSUCH')
    eq_(resp.status_code, 404)


@test_context.specialize(user=admin)
def test_make_tree(client):
    """Creating a tree makes a new tree with supplied values"""
    resp = client.put('/treestatus/trees/newtree', data=json.dumps(
        dict(tree='newtree', status='open', reason='green',
             message_of_the_day='look right or say goodnight')),
        headers=[('Content-Type', 'application/json')])
    eq_(resp.status_code, 204)
    resp = client.get('/treestatus/trees/newtree')
    eq_(json.loads(resp.data)['result'], dict(tree='newtree', status='open', reason='green',
                                              message_of_the_day='look right or say goodnight'))


@test_context.specialize(user=sheriff)
def test_make_tree_forbidden(client):
    """Creating a tree without admin privs fails"""
    resp = client.put('/treestatus/trees/tree9', data=json.dumps(
        dict(tree='tree9', status='open', reason='green',
             message_of_the_day='look right or say goodnight')),
        headers=[('Content-Type', 'application/json')])
    eq_(resp.status_code, 403)


@test_context.specialize(user=admin)
def test_make_tree_wrong_name(client):
    """Creating a tree with a different name in the path and the body fails"""
    resp = client.put('/treestatus/trees/sometree', data=json.dumps(
        dict(tree='othertree', status='open', reason='green',
             message_of_the_day='look right or say goodnight')),
        headers=[('Content-Type', 'application/json')])
    eq_(resp.status_code, 400)


@test_context.specialize(user=admin)
def test_make_tree_dup_name(client):
    """Creating a tree with an existing name fails"""
    resp = client.get('/treestatus/trees/tree1')
    eq_(resp.status_code, 200)
    resp = client.put('/treestatus/trees/tree1', data=json.dumps(
        dict(tree='tree1', status='open', reason='green',
             message_of_the_day='look right or say goodnight')),
        headers=[('Content-Type', 'application/json')])
    eq_(resp.status_code, 400)


@test_context.specialize(user=admin)
def test_delete_tree(client):
    """Deleting a tree .. deletes the tree"""
    resp = client.get('/treestatus/trees/tree1')
    eq_(resp.status_code, 200)
    resp = client.delete('/treestatus/trees/tree1')
    eq_(resp.status_code, 204)
    resp = client.get('/treestatus/trees/tree1')
    eq_(resp.status_code, 404)


@test_context.specialize(user=sheriff)
def test_delete_tree_no_perms(client):
    """Deleting a tree without admin perms fails"""
    resp = client.delete('/treestatus/trees/tree1')
    eq_(resp.status_code, 403)


@test_context.specialize(user=admin)
def test_delete_tree_nosuch(client):
    """Deleting a tree that does not exist fails"""
    resp = client.delete('/treestatus/trees/99999')
    eq_(resp.status_code, 404)


@test_context.specialize(user=sheriff)
def test_modify_tree(client):
    """Modifying a tree changes its message_of_the_day"""
    resp = client.patch('/treestatus/trees/tree1', data=json.dumps(
        dict(tree='tree1', status='closed', reason='because',
             message_of_the_day="if it don't fit force it")),
        headers=[('Content-Type', 'application/json')])
    eq_(resp.status_code, 204)
    resp = client.get('/treestatus/trees/tree1')
    eq_(json.loads(resp.data)['result'], dict(tree='tree1', status='closed', reason='because',
                                              message_of_the_day="if it don't fit force it"))


@test_context.specialize(user=admin)
def test_modify_tree_no_perms(client):
    """Modifying a tree without sheriff perms fails"""
    resp = client.patch('/treestatus/trees/tree1', data=json.dumps(
        dict(tree='tree1', status='closed', reason='because',
             message_of_the_day="if it don't fit force it")),
        headers=[('Content-Type', 'application/json')])
    eq_(resp.status_code, 403)


@test_context.specialize(user=sheriff)
def test_modify_tree_nosuch(client):
    """Modifying a tree that does not exist returns a 404 error"""
    resp = client.patch('/treestatus/trees/nosuch', data=json.dumps(
        dict(tree='tree1', status='closed', reason='because',
             message_of_the_day="if it don't fit force it")),
        headers=[('Content-Type', 'application/json')])
    eq_(resp.status_code, 404)


@test_context.specialize(user=sheriff)
def test_modify_tree_invalid_field(client):
    """Modifying a tree's name, status, or reason fails."""
    def mod(**mods):
        d = tree1_json.copy()
        d.update(mods)
        return d
    for t in [mod(tree='tree2'), mod(status='open'), mod(reason='i said so')]:
        resp = client.patch('/treestatus/trees/tree1',
                            data=json.dumps(t),
                            headers=[('Content-Type', 'application/json')])
        eq_(resp.status_code, 400)


@test_context
def test_get_logs(client):
    """Getting /treestatus/trees/tree1/logs results in a sorted list of log
    entries (newest first)"""
    resp = client.get('/treestatus/trees/tree1/logs')
    eq_(json.loads(resp.data)['result'], [{
        'tree': 'tree1',
        'tags': [],
        'who': 'dustin',
        'when': '2015-07-15T17:44:00',
        'reason': 'i really wanted to',
        'action': 'opened',
    }, {
        'tree': 'tree1',
        'tags': ['a', 'b'],
        'who': 'dustin',
        'when': '2015-07-14T17:44:00',
        'reason': 'because',
        'action': 'closed',
    }, {
        'tree': 'tree1',
        'tags': ['a'],
        'who': 'dustin',
        'when': '2015-07-13T17:44:00',
        'reason': 'i wanted to',
        'action': 'opened',
    }
    ])


@test_context
def test_get_logs_all(client, app):
    """Getting /treestatus/trees/tree1/logs with over 5 logs present
    results in only 5 logs, unless given ?all=1"""
    # add the log entries
    session = app.db.session('treestatus')
    for ln in range(5):
        l = model.DbLog(
            tree='tree1',
            when=datetime.datetime(2015, 6, 15, 17, 44, 00),
            who='jimmy',
            action='halfopen',
            reason='being difficult',
            tags=[])
        session.add(l)
    session.commit()

    resp = client.get('/treestatus/trees/tree1/logs')
    eq_(len(json.loads(resp.data)['result']), 5)

    resp = client.get('/treestatus/trees/tree1/logs?all=1')
    eq_(len(json.loads(resp.data)['result']), 8)


@test_context
def test_get_logs_nosuch(client):
    """Getting /treestatus/trees/NOSUCH/logs results in a 404"""
    resp = client.get('/treestatus/trees/NOSUCH/logs')
    eq_(resp.status_code, 404)


@test_context.specialize(db_setup=db_setup_stack)
def test_get_stack(client):
    """Getting /treestatus/stack gets the list of changes, most recent first"""
    resp = client.get('/treestatus/stack')
    res = json.loads(resp.data)
    # sort the tree lists, since order isn't specified
    res['result'][0]['trees'].sort()
    res['result'][1]['trees'].sort()
    eq_(res['result'], [{
        'id': 2,
        'trees': ['tree1', 'tree2'],
        'when': '2015-07-16T00:00:00',
        'who': 'dustin',
        'reason': 'bug 456',
        'status': 'closed',
    }, {
        'id': 1,
        'trees': ['tree0', 'tree1'],
        'who': 'dustin',
        'when': '2015-07-14T00:00:00',
        'reason': 'bug 123',
        'status': 'closed',
    }
    ])


@test_context.specialize(db_setup=db_setup_stack, user=sheriff)
def test_revert_stack(app, client):
    """REVERTing /treestatus/stack/N undoes the effects of that change and removes
    it from the stack"""
    resp = client.open('/treestatus/stack/2', method='REVERT')
    eq_(resp.status_code, 204)

    resp = client.get('/treestatus/trees')
    updated_status = sorted([(t['tree'], t['status'], t['reason'])
                             for t in json.loads(resp.data)['result'].values()])
    eq_(updated_status, [
        ('tree0', 'closed', 'bug 123'),
        ('tree1', 'closed', 'bug 123'),
        ('tree2', 'open', 'tree2'),
    ])

    resp = client.get('/treestatus/stack')
    res = json.loads(resp.data)
    res['result'][0]['trees'].sort()
    eq_(res['result'], [{
        'id': 1,
        'trees': ['tree0', 'tree1'],
        'who': 'dustin',
        'when': '2015-07-14T00:00:00',
        'reason': 'bug 123',
        'status': 'closed',
    }
    ])

    # reverts are logged, with no tags
    assert_logged(app, 'tree1', 'closed', 'bug 123')
    assert_logged(app, 'tree2', 'open', 'tree2')


@test_context.specialize(db_setup=db_setup_stack, user=admin)
def test_revert_stack_no_perms(app, client):
    """REVERTing a stack without sheriff privs fails"""
    resp = client.open('/treestatus/stack/2', method='REVERT')
    eq_(resp.status_code, 403)


@test_context.specialize(db_setup=db_setup_stack, user=sheriff)
def test_revert_stack_nosuch(client):
    """REVERTing /treestatus/stack/N where there's no such stack ID returns 404"""
    resp = client.open('/treestatus/stack/99', method='REVERT')
    eq_(resp.status_code, 404)


@test_context.specialize(db_setup=db_setup_stack, user=sheriff)
def test_delete_stack_change(client):
    """DELETE'ing /treestatus/stack/N removes the change from the stack but does
    not change the trees."""
    resp = client.get('/treestatus/trees')
    eq_(resp.status_code, 200)
    trees_before = json.loads(resp.data)['result']

    resp = client.open('/treestatus/stack/2', method='DELETE')
    eq_(resp.status_code, 204)

    resp = client.get('/treestatus/trees')
    eq_(resp.status_code, 200)
    trees_after = json.loads(resp.data)['result']
    eq_(trees_before, trees_after)

    resp = client.get('/treestatus/stack')
    res = json.loads(resp.data)
    res['result'][0]['trees'].sort()
    eq_(res['result'], [{
        'id': 1,
        'trees': ['tree0', 'tree1'],
        'who': 'dustin',
        'when': '2015-07-14T00:00:00',
        'reason': 'bug 123',
        'status': 'closed',
    }
    ])


@test_context.specialize(db_setup=db_setup_stack, user=admin)
def test_delete_stack_no_perms(app, client):
    """DELETE'ing a stack without sheriff privs fails"""
    resp = client.open('/treestatus/stack/2', method='DELETE')
    eq_(resp.status_code, 403)


@test_context.specialize(db_setup=db_setup_stack, user=sheriff)
def test_delete_stack_nosuch(client):
    """DELETE'ing /treestatus/stack/N where there's no such stack ID returns 404"""
    resp = client.open('/treestatus/stack/99', method='DELETE')
    eq_(resp.status_code, 404)


@test_context.specialize(db_setup=db_setup_stack, user=sheriff)
def test_update_trees_no_remember(app, client):
    """UPDATE'ing a tree without remembering changes updates those trees and
    clears out the stack for those trees."""
    update = {'trees': ['tree1'], 'status': 'open',
              'reason': 'fire extinguished',
              'tags': ['fire', 'water'],
              'remember': False}
    resp = client.open('/treestatus/trees', method='UPDATE',
                       data=json.dumps(update),
                       headers=[('Content-Type', 'application/json')])
    eq_(resp.status_code, 204)

    resp = client.get('/treestatus/trees')
    eq_(resp.status_code, 200)
    updated_status = sorted([(t['tree'], t['status'], t['reason'])
                             for t in json.loads(resp.data)['result'].values()])
    eq_(updated_status, [
        ('tree0', 'closed', 'bug 123'),
        ('tree1', 'open', 'fire extinguished'),
        ('tree2', 'closed', 'bug 456'),
    ])

    resp = client.get('/treestatus/stack')
    res = json.loads(resp.data)
    eq_(res['result'], [{
        'id': 2,
        'trees': ['tree2'],  # tree1 removed
        'when': '2015-07-16T00:00:00',
        'who': 'dustin',
        'reason': 'bug 456',
        'status': 'closed',
    }, {
        'id': 1,
        'trees': ['tree0'],  # tree1 removed
        'who': 'dustin',
        'when': '2015-07-14T00:00:00',
        'reason': 'bug 123',
        'status': 'closed',
    }
    ])

    assert_logged(app, 'tree1', 'open', 'fire extinguished',
                  tags=['fire', 'water'])


@test_context.specialize(db_setup=db_setup_stack, user=admin)
def test_update_trees_no_perms(app, client):
    """UPDATE'ing a tree without admin perms fails"""
    update = {'trees': ['tree1'], 'status': 'open',
              'reason': 'fire extinguished',
              'tags': ['fire', 'water'],
              'remember': False}
    resp = client.open('/treestatus/trees', method='UPDATE',
                       data=json.dumps(update),
                       headers=[('Content-Type', 'application/json')])
    eq_(resp.status_code, 403)


@test_context.specialize(db_setup=db_setup_stack, user=sheriff)
def test_update_trees_no_remember_remove_stack_entry(app, client):
    """UPDATE'ing a tree without remembering changes updates those trees and
    clears out the stack for those trees.  When a stack entry has no trees,
    it is removed."""
    update = {'trees': ['tree1', 'tree0'], 'status': 'open',
              'reason': 'fire extinguished',
              'tags': [],
              'remember': False}
    resp = client.open('/treestatus/trees', method='UPDATE',
                       data=json.dumps(update),
                       headers=[('Content-Type', 'application/json')])
    eq_(resp.status_code, 204)

    resp = client.get('/treestatus/trees')
    eq_(resp.status_code, 200)
    updated_status = sorted([(t['tree'], t['status'], t['reason'])
                             for t in json.loads(resp.data)['result'].values()])
    eq_(updated_status, [
        ('tree0', 'open', 'fire extinguished'),
        ('tree1', 'open', 'fire extinguished'),
        ('tree2', 'closed', 'bug 456'),
    ])

    resp = client.get('/treestatus/stack')
    res = json.loads(resp.data)
    eq_(res['result'], [{
        'id': 2,
        'trees': ['tree2'],  # tree1 removed
        'when': '2015-07-16T00:00:00',
        'who': 'dustin',
        'reason': 'bug 456',
        'status': 'closed',
    }])  # stack entry 1 removed

    assert_logged(app, 'tree0', 'open', 'fire extinguished')
    assert_logged(app, 'tree1', 'open', 'fire extinguished')


@test_context.specialize(db_setup=db_setup_stack, user=sheriff)
def test_update_trees_closed_without_tags(client):
    """UPDATE'ing trees to close them without tags is a bad request"""
    update = {'trees': ['tree1', 'tree0'], 'status': 'closed',
              'reason': 'bomb damage',
              'tags': [], 'remember': True}
    resp = client.open('/treestatus/trees', method='UPDATE',
                       data=json.dumps(update),
                       headers=[('Content-Type', 'application/json')])
    eq_(resp.status_code, 400)


@test_context.specialize(db_setup=db_setup_stack, user=sheriff)
def test_update_trees_remember(app, client):
    """UPDATE'ing a tree and remembering changes updates those trees and
    adds a stack entry."""
    update = {'trees': ['tree1', 'tree0'], 'status': 'closed',
              'reason': 'bomb damage',
              'tags': ['c4'], 'remember': True}
    with set_time(datetime.datetime(2015, 7, 21, 0, 0, 0)):
        resp = client.open('/treestatus/trees', method='UPDATE',
                           data=json.dumps(update),
                           headers=[('Content-Type', 'application/json')])
    eq_(resp.status_code, 204)

    resp = client.get('/treestatus/trees')
    eq_(resp.status_code, 200)
    updated_status = sorted([(t['tree'], t['status'], t['reason'])
                             for t in json.loads(resp.data)['result'].values()])
    eq_(updated_status, [
        ('tree0', 'closed', 'bomb damage'),
        ('tree1', 'closed', 'bomb damage'),
        ('tree2', 'closed', 'bug 456'),
    ])

    resp = client.get('/treestatus/stack')
    res = json.loads(resp.data)
    for st in res['result']:
        st['trees'].sort()
    eq_(res['result'], [{
        'id': 3,
        'trees': ['tree0', 'tree1'],
        'when': '2015-07-21T00:00:00',
        'who': 'human:user@domain.com',
        'reason': 'bomb damage',
        'status': 'closed',
    }, {
        'id': 2,
        'trees': ['tree1', 'tree2'],
        'when': '2015-07-16T00:00:00',
        'who': 'dustin',
        'reason': 'bug 456',
        'status': 'closed',
    }, {
        'id': 1,
        'trees': ['tree0', 'tree1'],
        'who': 'dustin',
        'when': '2015-07-14T00:00:00',
        'reason': 'bug 123',
        'status': 'closed',
    }
    ])

    assert_logged(app, 'tree0', 'closed', 'bomb damage', tags=['c4'])
    assert_logged(app, 'tree1', 'closed', 'bomb damage', tags=['c4'])