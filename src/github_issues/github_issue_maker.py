from __future__ import print_function
import os
import sys
import json
import requests
import time

if __name__=='__main__':
    SRC_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.append(SRC_ROOT)

from jinja2 import Template
from jinja2 import Environment, PackageLoader

from utils.msg_util import *
from github_issues.md_translate import translate_for_github
from github_issues.milestone_helper import MilestoneHelper
from github_issues.label_helper import LabelHelper
import csv

from settings.base import get_github_auth, REDMINE_SERVER

import pygithub3

class GithubIssueMaker:
    """
    Given a Redmine issue in JSON format, create a GitHub issue.
    These issues should be moved from Redmine in order of issue.id.  This will allow mapping of Redmine issue ID's against newly created Github issued IDs.  e.g., can translate related issues numbers, etc.
    """
    ISSUE_STATE_CLOSED = ['Rejected', 'Closed', 'Resolved']

    def __init__(self, user_map_helper=None, label_mapping_filename=None, milestone_mapping_filename=None):
        self.github_conn = None
        self.comments_service = None
        self.milestone_manager = MilestoneHelper(milestone_mapping_filename)
        self.label_helper = LabelHelper(label_mapping_filename)
        self.jinja_env = Environment(loader=PackageLoader('github_issues', 'templates'))
        self.user_map_helper = user_map_helper

    def get_comments_service(self):
        if self.comments_service is None:
            self.comments_service = pygithub3.services.issues.Comments(**get_github_auth())

        return self.comments_service


    def get_github_conn(self):

        if self.github_conn is None:
            self.github_conn = pygithub3.Github(**get_github_auth())
        return self.github_conn

    def format_name_for_github(self, author_name, include_at_sign=True):
        """
        (1) Try the user map
        (2) If no match, return the name
        """
        if not author_name:
            return None

        if self.user_map_helper:
            github_name = self.user_map_helper.get_github_user(author_name, include_at_sign)
            if github_name is not None:
                return github_name
        return author_name


    def get_redmine_assignee_name(self, redmine_issue_dict):
        """
        If a redmine user has a github account mapped, add the person as the assignee

        "assigned_to": {
            "id": 4,
            "name": "Philip Durbin"
        },
        /cc @kneath @jresig
        """
        if not type(redmine_issue_dict) is dict:
            return None

        redmine_name = redmine_issue_dict.get('assigned_to', {}).get('name', None)
        if redmine_name is None:
            return None

        return redmine_name


    def get_assignee(self, redmine_issue_dict):
        """
        If a redmine user has a github account mapped, add the person as the assignee

        "assigned_to": {
            "id": 4,
            "name": "Philip Durbin"
        },
        /cc @kneath @jresig
        """
        if not type(redmine_issue_dict) is dict:
            return None

        redmine_name = redmine_issue_dict.get('assigned_to', {}).get('name', None)
        if redmine_name is None:
            return None

        github_username = self.format_name_for_github(redmine_name, include_at_sign=False)

        return github_username


    def update_github_issue_with_related(self, redmine_json_fname, redmine2github_issue_map, include_redmine_links):
        """
        Update a GitHub issue with related tickets as specfied in Redmine

        - Read the current github description
        - Add related notes to the bottom of description
        - Update the description

        "relations": [
              {
                  "delay": null,
                  "issue_to_id": 4160,
                  "issue_id": 4062,
                  "id": 438,
                  "relation_type": "relates"
              },
              {
                  "delay": null,
                  "issue_to_id": 3643,
                  "issue_id": 4160,
                  "id": 439,
                  "relation_type": "relates"
              }
          ],
          "id": 4160,
        """
        if not os.path.isfile(redmine_json_fname):
            msgx('ERROR.  update_github_issue_with_related. file not found: %s' % redmine_json_fname)

        #msg('issue map: %s' % redmine2github_issue_map)

        json_str = open(redmine_json_fname, 'rU').read()
        rd = json.loads(json_str)       # The redmine issue as a python dict
        #msg('rd: %s' % rd)

        if rd.get('relations', None) is None:
            msg('no relations')
            return

        redmine_issue_num = rd.get('id', None)
        if redmine_issue_num is None:
            return

        github_issue_num = redmine2github_issue_map.get(str(redmine_issue_num), None)
        if github_issue_num is None:
            msg('Redmine issue not in nap')
            return


        # Related tickets under 'relations'
        #
        github_related_tickets = []
        original_related_tickets = []
        for rel in rd.get('relations'):
            issue_to_id = rel.get('issue_to_id', None)
            if issue_to_id is None:
                continue
            if rd.get('id') == issue_to_id:  # skip relations pointing to this ticket
                continue

            original_related_tickets.append(issue_to_id)
            related_github_issue_num = redmine2github_issue_map.get(str(issue_to_id), None)
            msg(related_github_issue_num)
            if related_github_issue_num:
                github_related_tickets.append(related_github_issue_num)
        github_related_tickets.sort()
        original_related_tickets.sort()
        #
        # end: Related tickets under 'relations'


        # Related tickets under 'children'
        #
        # "children": [{ "tracker": {"id": 2, "name": "Feature"    }, "id": 3454, "subject": "Icons in results and facet"    }, ...]
        #
        github_child_tickets = []
        original_child_tickets = []

        child_ticket_info = rd.get('children', [])
        if child_ticket_info:
            for ctick in child_ticket_info:

                child_id = ctick.get('id', None)
                if child_id is None:
                    continue

                original_child_tickets.append(child_id)
                child_github_issue_num = redmine2github_issue_map.get(str(child_id), None)

                msg(child_github_issue_num)
                if child_github_issue_num:
                    github_child_tickets.append(child_github_issue_num)
            original_child_tickets.sort()
            github_child_tickets.sort()
        #
        # end: Related tickets under 'children'


        #
        # Update github issue with related and child tickets
        #
        #
        if len(original_related_tickets) == 0 and len(original_child_tickets)==0:
            return

        # Format related and children ticket numbers
        original_issues_str = ""
        original_children_str = ""
        if include_redmine_links:
            original_issues_formatted = [ """[%s](%s)""" % (x, self.format_redmine_issue_link(x)) for x in original_related_tickets]
            original_issues_str = ', '.join(original_issues_formatted)
            msg('Redmine related issues: %s' % original_issues_str)

            original_children_formatted = [ """[%s](%s)""" % (x, self.format_redmine_issue_link(x)) for x in original_child_tickets]
            original_children_str = ', '.join(original_children_formatted)
            msg('Redmine sub-issues: %s' % original_children_str)

        related_issues_formatted = [ '#%d' % int(x) for x in github_related_tickets]
        related_issue_str = ', '.join(related_issues_formatted)
        msg('Github related issues: %s' % related_issue_str)

        github_children_formatted = [ '#%d' % x for x in github_child_tickets]
        github_children_str = ', '.join(github_children_formatted)
        msg('Github sub-issues: %s' % github_children_str)

        try:
            issue = self.get_github_conn().issues.get(number=github_issue_num)
        except pygithub3.exceptions.NotFound:
            msg('Issue not found!')
            return

        template = self.jinja_env.get_template('related_issues.md')

        template_params = { 'original_description' : issue.body\
                            , 'original_issues' : original_issues_str\
                            , 'related_issues' : related_issue_str\
                            , 'child_issues_original' : original_children_str\
                            , 'child_issues_github' : github_children_str\

                            }

        updated_description = template.render(template_params)

        issue = self.get_github_conn().issues.update(number=github_issue_num, data={'body':updated_description})

        msg('Issue updated!')#' % issue.body)


    def format_redmine_issue_link(self, issue_id):
        if issue_id is None:
            return None

        return os.path.join(REDMINE_SERVER, 'issues', '%d' % issue_id)


    def close_github_issue(self, github_issue_num):

        if not github_issue_num:
            return False
        msgt('Close issue: %s' % github_issue_num)

        try:
             issue = self.get_github_conn().issues.get(number=github_issue_num)
        except pygithub3.exceptions.NotFound:
             msg('Issue not found!')
             return False

        if issue.state in self.ISSUE_STATE_CLOSED:
            msg('Already closed')
            return True

        updated_issue = self.get_github_conn().issues.update(number=github_issue_num, data={'state': 'closed' })
        if not updated_issue:
            msg('Failed to close issue')
            return False

        if updated_issue.state in self.ISSUE_STATE_CLOSED:
            msg('Issue closed')
            return True

        msg('Failed to close issue')
        return False



    def make_github_issue(self, redmine_json_fname, **kwargs):
        """
        Create a GitHub issue from JSON for a Redmine issue.

        - Format the GitHub description to include original redmine info: author, link back to redmine ticket, etc
        - Add/Create Labels
        - Add/Create Milestones
        """
        if not os.path.isfile(redmine_json_fname):
            msgx('ERROR.  make_github_issue. file not found: %s' % redmine_json_fname)

        include_comments = kwargs.get('include_comments', True)
        include_assignee = kwargs.get('include_assignee', True)
        include_redmine_links = kwargs.get('include_redmine_links', True)

        json_str = open(redmine_json_fname, 'rU').read()
        rd = json.loads(json_str)       # The redmine issue as a python dict

        #msg(json.dumps(rd, indent=4))
        msg('Attempt to create issue: [#%s][%s]' % (rd.get('id'), rd.get('subject') ))

        # (1) Format the github issue description
        #
        #
        template = self.jinja_env.get_template('description.md')

        author_name = rd.get('author', {}).get('name', None)
        author_github_username = self.format_name_for_github(author_name)
        redmine_link = ""
        if include_redmine_links:
            redmine_link = self.format_redmine_issue_link(rd.get('id'))

        desc_dict = {'description' : translate_for_github(rd.get('description', 'no description'))\
                    , 'redmine_link' : redmine_link
                    , 'redmine_issue_num' : rd.get('id')\
                    , 'start_date' : rd.get('start_date', None)\
                    , 'author_name' : author_name\
                    , 'author_github_username' : author_github_username\
                    , 'redmine_assignee' : self.get_redmine_assignee_name(rd)
        }

        description_info = template.render(desc_dict)

        #
        # (2) Create the dictionary for the GitHub issue--for the github API
        #
        #self.label_helper.clear_labels(151)
        github_issue_dict = { 'title': rd.get('subject')\
                    , 'body' : description_info\
                    , 'labels' : self.label_helper.get_label_names_from_issue(rd)
                    }

        milestone_number = self.milestone_manager.get_create_milestone(rd)
        if milestone_number:
            github_issue_dict['milestone'] = milestone_number

        if include_assignee:
            assignee = self.get_assignee(rd)
            if assignee:
                github_issue_dict['assignee'] = assignee

        msg( github_issue_dict)

        #
        # (4) Add the redmine comments (journals) as github comments
        #
        comments_data = []
        if include_comments:
            comments_data = self.add_comments_for_issue(rd)


        issue_data = {
          'issue' : {
            'title' : rd.get('subject'),
            'body' : description_info,
            'created_at' : rd.get('created_on', None),
            'assignee' : assignee,
            'milestone' : milestone_number,
            'closed' : self.is_redmine_issue_closed(rd),
            'labels' : self.label_helper.get_label_names_from_issue(rd),
          },
          'comments' : comments_data,
        }

        return self.import_issue(issue_data)

    # use the github issue import api to import an issue in one api call (with correct dates)
    # see: https://gist.github.com/jonmagic/5282384165e0f86ef105
    def import_issue(self, issue_data):

        url = 'https://api.github.com/repos/{}/{}/import/issues'.format(get_github_auth()['user'], get_github_auth()['repo'])

        headers = {
            'Accept' : 'application/vnd.github.golden-comet-preview+json'
        }

        auth = (get_github_auth()['login'], get_github_auth()['password'])

        r = requests.post(url, data = json.dumps(issue_data), auth = auth, headers = headers)

        if r.status_code != 200 and r.status_code != 202:
            msgx('Error importing issue. github http response status %s. json received: %s' % (r.status_code, r.json()))
        github_response = r.json()

        # TODO: need error handling
        #       check github json for status: failed
        print(github_response)

        return github_response['id']

    # get a map of temporary github import ids to the final issue id on github
    def get_github_ids(self, start_time):

        # now check on the status, so that we can get the resulting github issue id
        url = 'https://api.github.com/repos/{}/{}/import/issues?since={}'.format(get_github_auth()['user'], get_github_auth()['repo'], str(start_time))

        headers = {
            'Accept' : 'application/vnd.github.golden-comet-preview+json'
        }

        auth = (get_github_auth()['login'], get_github_auth()['password'])

        github_id_map = dict()

        pending_count = 1
        while pending_count > 0:

            pending_count = 0

            r = requests.get(url, auth = auth, headers = headers)

            if r.status_code != 200 and r.status_code != 202:
                msgx('Error checking status of issue. github http response status %s. json received: %s' % (r.status_code, r.json()))
            github_response = r.json()

            for issue_response in github_response:
                if 'issue_url' not in issue_response:
                    if issue_response['status'] == 'pending':
                        pending_count += 1
                    else:
                        msgx("Couldn't find issue URL in github response: %s" % issue_response)
                else:
                    issue_url = issue_response['issue_url']
                    github_id_map[issue_response['id']] = issue_url.rsplit('/', 1)[-1]
            if pending_count > 0:
                msgt("%d issue imports are still pending, sleeping then retrying id check" % pending_count)
                time.sleep(5) # wait for a second to see if pending issues resolve

        return github_id_map

    def is_redmine_issue_closed(self, redmine_issue_dict):
        """
        "status": {
            "id": 5,
            "name": "Completed"
        },
        """
        if not type(redmine_issue_dict) == dict:
            return False

        status_info = redmine_issue_dict.get('status', None)
        if not status_info:
            return False

        if status_info.has_key('name') and status_info.get('name', None) in self.ISSUE_STATE_CLOSED:
            return True

        return False


    def add_comments_for_issue(self, rd):

        journals = rd.get('journals', None)
        comment_template = self.jinja_env.get_template('comment.md')

        comments_data = []

        for j in journals:

            author_name = j.get('user', {}).get('name', None)
            author_github_username = self.format_name_for_github(author_name)

            note_dict = {
                'description' : translate_for_github(j.get('notes', 'No text.')),
                'note_date' : j.get('created_on', None),
                'author_name' : author_name,
                'author_github_username' : author_github_username,
            }

            # check if this comment changed the ticket to its current status
            # if so, record status change in comment
            # TODO: would be nice to have the status ids mapped, and record
            #       every status change in the comments. right now we only
            #       have the status name of the current status of the ticket.
            #       would need to get a map of status id to status name from
            #       redmine. then add {{status_old}} to {{status_new}} in
            #       the comment.md template
            if 'details' in j:
                for detail in j['details']:
                    if detail['name'] == 'status_id' and int(detail['new_value']) == rd['status']['id']:
                        note_dict['status_new'] = rd['status']['name']

            if 'notes' not in note_dict and 'status_new' not in note_dict:
                continue

            comment_info = comment_template.render(note_dict)

            comment = {
                'body' : comment_info,
                'created_at' : j.get('created_on', None),
            }
            comments_data.append(comment)

        return comments_data

if __name__=='__main__':
    #auth = dict(login=GITHUB_LOGIN, password=GITHUB_PASSWORD_OR_PERSONAL_ACCESS_TOKEN, repo=GITHUB_TARGET_REPOSITORY, user=GITHUB_TARGET_USERNAME)
    #milestone_service = pygithub3.services.issues.Milestones(**auth)
    #comments_service = pygithub3.services.issues.Comments(**auth)
    #fname = 03385.json'
    #gm.make_github_issue(fname, {})

    import time

    issue_filename = '/Users/rmp553/Documents/iqss-git/redmine2github/working_files/redmine_issues/2014-0702/04156.json'
    gm = GithubIssueMaker()
    for x in range(100, 170):
        gm.close_github_issue(x)
    #gm.make_github_issue(issue_filename, {})

    sys.exit(0)
    root_dir = '/Users/rmp553/Documents/iqss-git/redmine2github/working_files/redmine_issues/2014-0702/'

    cnt =0
    for fname in os.listdir(root_dir):
        if fname.endswith('.json'):

            num = int(fname.replace('.json', ''))
            if num < 3902: continue
            msg('Add issue from: %s' % fname)
            cnt+=1
            fullname = os.path.join(root_dir, fname)
            gm.make_github_issue(fullname, {})
            if cnt == 150:
                break

            if cnt%50 == 0:
                msg('sleep 2 secs')
                time.sleep(2)

            #sys.exit(0)






