#!/usr/bin/env python
# -*- coding: utf-8 -*-
# vim:ts=4:sw=4:softtabstop=4:smarttab:expandtab

from __future__ import unicode_literals, division, absolute_import, print_function

import sys
import os
from datetime import datetime, timedelta
from lxml import objectify

from compatibility_utils import PY2

from updatecheck import UpdateChecker
from parsing_engine import MarkupParser
# from tk_tooltips import CreateToolTip
from dialogs import guiConfig

if PY2:
    import Tkinter as tkinter
    import ttk as tkinter_ttk
    import Tkconstants as tkinter_constants
    import tkMessageBox as tkinter_msgbox
    import tkFont
    text_type = unicode
else:
    import tkinter
    import tkinter.ttk as tkinter_ttk
    import tkinter.constants as tkinter_constants
    import tkinter.messagebox as tkinter_msgbox
    import tkinter.font as tkFont
    text_type = str


gui_selections = {
    'action' : 0,
    'tag'    : 0,
    'attrs'  : 0,
}

font_tweaks = {
    'font_family' : 'Helvetica',
    'font_size'   : '10',
}

miscellaneous_settings = {
    'windowGeometry' : None,
}

update_settings = {
    'last_time_checked'   : str(datetime.now() - timedelta(hours=13)),
    'last_online_version' : '0.0.0',
}

# To add a new tag, add it to taglist and add a list of tags it can be changed to to combobox_defaults
taglist = ['span', 'div', 'p', 'i', 'em', 'b', 'strong', 'u', 'small', 'a', 'blockquote',
           'header', 'section', 'footer', 'nav', 'article']

combobox_defaults = {
    'span_changes'        : ['em', 'strong', 'i', 'b', 'small', 'u'],
    'div_changes'         : ['p', 'blockquote'],
    'p_changes'           : ['div'],
    'i_changes'           : ['em', 'span'],
    'em_changes'          : ['i', 'span'],
    'b_changes'           : ['strong', 'span'],
    'strong_changes'      : ['b', 'span'],
    'u_changes'           : ['span'],
    'small_changes'       : ['span'],
    'a_changes'           : [],
    'blockquote_changes'  : ['div'],
    'header_changes'      : ['div'],
    'section_changes'     : ['div'],
    'footer_changes'      : ['div'],
    'nav_changes'         : ['div'],
    'article_changes'     : ['div'],
    'attrs'               : ['class', 'id', 'style', 'href'],
}

CONTEXT_BINDINGS = '<Button-3><ButtonRelease-3>'
if sys.platform.startswith('darwin'):
    CONTEXT_BINDINGS = '<Button-2><ButtonRelease-2>'

prefs = {}
BAIL_OUT = False


# Some keys were renamed along the way. Convert users existing prefs to new ones.
def fix_old_keys(combo_values):
    if 'sec_changes' in combo_values:
        combo_values['section_changes'] = combo_values.pop('sec_changes')
    if 'block_changes' in combo_values:
        combo_values['blockquote_changes'] = combo_values.pop('block_changes')
    return combo_values


def check_for_new_prefs(prefs_group, default_values):
    ''' Make sure that adding new tags doesn't mean that the user has
    to delete their preferences json and start all over. Piecemeal defaults
    instead of the wholesale approach. '''
    for key, value in default_values.items():
        if key not in prefs_group:
            prefs_group[key] = value


def valid_attributes(tattr):
    ''' This is not going to catch every, single way a user can screw this up, but
    it's going to ensure that they can't enter an attribute string that's going to:
    a) hang the attribute parser
    b) make the xhmtl invalid '''

    # Make a fake xml string and try to parse the attributes of the "stuff" element
    # with lxml's objectify.
    template ='''<root><stuff %s>dummy</stuff></root>''' % tattr
    try:
        root = objectify.fromstring(template)
        dummy = root.stuff.attrib
    except:
        return False
    return True


class guiMain(tkinter.Frame):
    def __init__(self, parent, bk):
        tkinter.Frame.__init__(self, parent, border=5)
        self.parent = parent
        self.taglist = taglist
        # Edit Plugin container object
        self.bk = bk
        # Handy prefs groupings
        self.font_tweaks = prefs['font_tweaks']
        self.gui_prefs = prefs['gui_selections']
        self.misc_prefs = prefs['miscellaneous_settings']
        self.update_prefs = prefs['update_settings']
        self.combobox_values = prefs['combobox_values']
        self.criteria ={}
        # Check online github files for newer version
        self.update, self.newversion = self.check_for_update()

        if self.misc_prefs['windowGeometry'] is None:
            # Sane geometry defaults
            self.parent.update_idletasks()
            w = self.parent.winfo_screenwidth()
            h = self.parent.winfo_screenheight()
            rootsize = (420, 325)
            x = w/2 - rootsize[0]/2
            y = h/2 - rootsize[1]/2
            self.misc_prefs['windowGeometry'] = ('%dx%d+%d+%d' % (rootsize + (x, y)))

        self.initUI()
        parent.protocol('WM_DELETE_WINDOW', self.quitApp)

    def initUI(self):
        ''' Build the GUI and assign variables and handler functions to elements. '''
        self.parent.title(self.bk._w.plugin_name)
        self.NO_ATTRIB_STR = 'No attributes ("naked" tag)'
        self.NO_CHANGE_STR = 'No change'
        # Create context menu for plugin customization and bind it
        # to the right-click/third-button mouse event
        self.context_menu = tkinter.Menu(self, tearoff=0, takefocus=0)
        self.context_menu.add_command(label='Customize Plugin', command=self.showConfig)
        self.parent.bind(CONTEXT_BINDINGS, self.showMenu)

        body = tkinter.Frame(self)
        body.pack(fill=tkinter_constants.BOTH)

        # Action type combobox -- Modify/Delete
        actionFrame = tkinter.Frame(body, pady=3)
        label = tkinter.Label(actionFrame, text='Action type:')
        label.pack(side=tkinter_constants.LEFT, fill=tkinter_constants.Y)
        self.action_combo_value = tkinter.StringVar()
        self.action_combo = tkinter_ttk.Combobox(actionFrame, width=22, textvariable=self.action_combo_value)
        self.action_combo['values'] = ('Modify', 'Delete')
        self.action_combo.current(self.gui_prefs['action'])
        self.action_combo.bind('<<ComboboxSelected>>', self.action_change_actions)
        # CreateToolTip(self.action_combo, 'Modify a tag or delete it entirely?')
        self.action_combo.pack(side=tkinter_constants.RIGHT, fill=tkinter_constants.Y)
        actionFrame.pack(side=tkinter_constants.TOP, fill=tkinter_constants.BOTH)

        # Tag name selection combobox -- from taglist
        targetTagFrame = tkinter.Frame(body, pady=3)
        label = tkinter.Label(targetTagFrame, text='Tag name:')
        label.pack(side=tkinter_constants.LEFT, fill=tkinter_constants.Y)
        self.tag_combo_value = tkinter.StringVar()
        self.tag_combo = tkinter_ttk.Combobox(targetTagFrame, width=22, textvariable=self.tag_combo_value)
        self.tag_combo['values'] = tuple(self.taglist)
        try:
            self.tag_combo.current(self.gui_prefs['tag'])
        except:
            self.tag_combo.current(0)
        self.tag_combo.bind('<<ComboboxSelected>>', self.tag_change_actions)
        # CreateToolTip(self.tag_combo, 'Which (x)html element do you wish to work with?')
        self.tag_combo.pack(side=tkinter_constants.RIGHT, fill=tkinter_constants.Y)
        targetTagFrame.pack(side=tkinter_constants.TOP, fill=tkinter_constants.BOTH)

        # Attribute name combobox -- variable, based on prefs/defaults
        attrsFrame = tkinter.Frame(body, pady=3)
        label = tkinter.Label(attrsFrame, text='Having the attribute:')
        label.pack(side=tkinter_constants.LEFT, fill=tkinter_constants.Y)
        self.attrs_combo_value = tkinter.StringVar()
        self.attrs_combo = tkinter_ttk.Combobox(attrsFrame, width=22, textvariable=self.attrs_combo_value)
        self.update_attrs_combo()
        try:
            self.attrs_combo.current(self.gui_prefs['attrs'])
        except:
            self.attrs_combo.current(0)
        self.attrs_combo.bind('<<ComboboxSelected>>', self.attribute_change_actions)
        # CreateToolTip(self.attrs_combo, 'Which attribute do you want to use to narrow the results?')
        self.attrs_combo.pack(side=tkinter_constants.RIGHT, fill=tkinter_constants.Y)
        attrsFrame.pack(side=tkinter_constants.TOP, fill=tkinter_constants.BOTH)

        # Value text-entry for the attribute selected in the Attribute combobox
        valueFrame = tkinter.Frame(body, pady=3)
        label = tkinter.Label(valueFrame, text='Whose value is (no quotes):')
        label.pack(side=tkinter_constants.LEFT, fill=tkinter_constants.Y)
        self.attrvalue_entry_value = tkinter.StringVar()
        self.attrvalue_entry = tkinter.Entry(valueFrame, textvariable=self.attrvalue_entry_value)
        self.attrvalue_entry.pack(side=tkinter_constants.LEFT, fill=tkinter_constants.X, expand=True)
        # CreateToolTip(self.attrvalue_entry, 'What value for the selected attribute should be used to narrow the results even more?')
        self.srch_type = tkinter.StringVar()
        self.regex_checkbox = tkinter.Checkbutton(valueFrame, text="Regex", variable=self.srch_type, onvalue='regex', offvalue='normal')
        self.regex_checkbox.deselect()
        self.regex_checkbox.pack(side=tkinter_constants.RIGHT, fill=tkinter_constants.Y)
        # CreateToolTip(self.regex_checkbox, 'Is your attribute value a literal string or a regular expression?')
        valueFrame.pack(side=tkinter_constants.TOP, fill=tkinter_constants.BOTH)
        if self.attrs_combo_value.get() == self.NO_ATTRIB_STR:
            self.attrvalue_entry.config(state='disabled')
            self.regex_checkbox.config(state='disabled')

        # New tag combobox -- changes based on the first Tag combobox
        newtagFrame = tkinter.Frame(body, pady=3)
        label = tkinter.Label(newtagFrame, text='Change tag to:')
        label.pack(side=tkinter_constants.LEFT, fill=tkinter_constants.Y)
        self.newtag_combo_value = tkinter.StringVar()
        self.newtag_combo = tkinter_ttk.Combobox(newtagFrame, width=22, textvariable=self.newtag_combo_value)
        self.tag_change_actions(None)
        # CreateToolTip(self.newtag_combo, 'Do you want to change the tag to a new element or keep it the same?')
        self.newtag_combo.pack(side=tkinter_constants.RIGHT, fill=tkinter_constants.Y)
        newtagFrame.pack(side=tkinter_constants.TOP, fill=tkinter_constants.BOTH)
        if self.action_combo_value.get() == 'Delete':
            self.newtag_combo.config(state='disabled')

        # Attributes text entry -- used to replace the existing attributes with ones the user provides
        attrStrFrame = tkinter.Frame(body, bd=2, pady=3, relief=tkinter_constants.GROOVE)
        label = tkinter.Label(attrStrFrame, text='New attribute string (all attributes):')
        label.pack(anchor=tkinter_constants.NW, fill=tkinter_constants.Y)
        self.attrStr_entry_value = tkinter.StringVar()
        self.attrStr_entry = tkinter.Entry(attrStrFrame, textvariable=self.attrStr_entry_value)
        # CreateToolTip(self.attrStr_entry, 'What (if anything) do you want the resulting attributes to be (empty means none)?')
        self.attrStr_entry.pack(side=tkinter_constants.LEFT, fill=tkinter_constants.X, expand=True)
        # Copy existing attributes checkbox
        self.copy_attrs = tkinter.IntVar()
        self.copy_attrs_checkbox = tkinter.Checkbutton(attrStrFrame,
                    text="Copy existing", command=self.copy_existing_chkbox_actions, variable=self.copy_attrs, onvalue=1, offvalue=0)
        # CreateToolTip(self.copy_attrs_checkbox, 'Copy the existing attibutes of the tag unchanged?')
        self.copy_attrs_checkbox.pack(side=tkinter_constants.RIGHT, fill=tkinter_constants.Y)
        attrStrFrame.pack(side=tkinter_constants.TOP, fill=tkinter_constants.BOTH)
        if self.action_combo_value.get() == 'Delete':
            self.attrStr_entry.config(state='disabled')
            self.copy_attrs_checkbox.config(state='disabled')

        # Results textbox/scrollbar
        results_frame = tkinter.Frame(body, bd=2, pady=3)
        results_label = tkinter.Label(results_frame, text='Results:')
        results_label.pack(side=tkinter_constants.TOP, fill=tkinter_constants.BOTH)
        scrollbar = tkinter.Scrollbar(results_frame, orient=tkinter_constants.VERTICAL)
        self.results = tkinter.Text(results_frame, height=600, yscrollcommand=scrollbar.set, wrap=tkinter_constants.WORD)
        scrollbar.config(command=self.results.yview)
        scrollbar.pack(side=tkinter_constants.RIGHT, fill=tkinter_constants.Y)
        results_frame.pack(side=tkinter_constants.TOP, fill=tkinter_constants.BOTH)

        # Dialog button box
        buttons = tkinter.Frame()
        self.gbutton = tkinter.Button(buttons, text='Process', command=self.cmdDo)
        # CreateToolTip(self.gbutton, 'Process the selected (x)html files in Book View with your choices.')
        self.gbutton.pack(side=tkinter_constants.LEFT, fill=tkinter_constants.BOTH, expand=True)
        self.bbutton = tkinter.Button(buttons, text='Abort Changes', command=self.cmdBailOut)
        # CreateToolTip(self.bbutton, 'Abort all modifications and exit.')
        self.bbutton.pack(side=tkinter_constants.LEFT, fill=tkinter_constants.BOTH, expand=True)
        self.bbutton.config(state='disabled')
        self.qbutton = tkinter.Button(buttons, text='Quit', command=self.quitApp)
        # CreateToolTip(self.qbutton, 'Close this dialog.')
        self.qbutton.pack(side=tkinter_constants.LEFT, fill=tkinter_constants.BOTH, expand=True)
        buttons.pack(side=tkinter_constants.BOTTOM, pady=5, fill=tkinter_constants.BOTH)

        self.results.pack(side=tkinter_constants.TOP, fill=tkinter_constants.BOTH, expand=True)

        # Get the saved window geometry settings
        self.parent.geometry(self.misc_prefs['windowGeometry'])
        self.parent.deiconify()
        self.parent.lift()

        # Pop the update message if newer plugin version is avialable
        if self.update:
            self.update_msgbox()

    def showMenu(self, e):
        '''show the customization context menu when right-clicking'''
        self.context_menu.post(e.x_root, e.y_root)

    def cmdBailOut(self):
        '''set the global bail out variable to true and quit'''
        global BAIL_OUT
        BAIL_OUT = True
        self.quitApp()

    def cmdDo(self):
        '''The main event

        Gather the parameters to give to the parser (in the criteria dictionary)

        The criteria parameter dictionary specs:

        criteria['html']              Param 1 - the contents of the (x)html file: unicode text.
        criteria['action']            Param 2 - action to take: unicode text ('modify' or 'delete')
        criteria['tag']               Param 3 - tag to alter/delete: unicode text
        criteria['attrib']            Param 4 - attribute to use in match: unicode text or None
        criteria['srch_str']          Param 5 - value of the attribute to use in match: unicode text (literal or regexp) or None
        criteria['srch_method']       Param 6 - is the value given literal or a regexp: boolean
        criteria['new_tag']           Param 7 - tag to change to: unicode text, or None
        criteria['new_str']           Param 8 - new attributes to be written: unicode text
        criteria['copy']              Param 9 - copy the existing attributes verbatim?: boolean
        '''
        # Param 2 - action to take
        self.criteria['action'] = self.action_combo_value.get().lower()

        # Param 3 - tag to alter/delete
        self.criteria['tag'] = self.tag_combo_value.get()

        # Param 4 - attribute to use in match
        if self.attrs_combo_value.get() == self.NO_ATTRIB_STR:
            self.criteria['attrib'] = None
        else:
            self.criteria['attrib'] = self.attrs_combo_value.get()

        # Param 5 - value of the attribute to use in match
        self.criteria['srch_str'] = self.attrvalue_entry_value.get()
        if not len(self.criteria['srch_str']):
            self.criteria['srch_str'] = None
        # Error checking: have to have a value/expression if you've chosen an attribute
        if self.criteria['srch_str'] is None and self.criteria['attrib'] is not None:
            title = 'Error'
            msg = 'Must enter a value for the attribute.'
            return tkinter_msgbox.showerror(title, msg)

        # Param 6 - is the value given literal or a regexp?
        self.criteria['srch_method'] = self.srch_type.get()

        # Param 7 - change to new tag or keep the same?
        if self.newtag_combo_value.get() ==self.NO_CHANGE_STR:
            self.criteria['new_tag'] = None
        else:
            self.criteria['new_tag'] = self.newtag_combo_value.get()

        # Error checking: this scenario results in "changing" the markup to exactly what it is now. Avoid.
        if self.criteria['action'] == 'modify' and self.criteria['new_tag'] is None and self.copy_attrs.get():
            title = 'Error'
            msg = 'What--exactly--would that achieve?'
            return tkinter_msgbox.showerror(title, msg)

        tattr = self.attrStr_entry_value.get()  # .replace("'", '"')
        if not len(tattr):
            tattr = ''
        # Error checking: Use lxml's objectify to quickly test the new attribute string for syntax.
        if not valid_attributes(tattr):
            title = 'Error'
            msg = 'There\'s an issue with your replacement attributes. Please check your syntax.'
            return tkinter_msgbox.showerror(title, msg)
        # Param 8 - new attributes to be written.
        self.criteria['new_str'] = tattr

        # Param 9 - copy the existing attributes verbatim?
        self.criteria['copy'] = False
        if self.copy_attrs.get():
            self.criteria['copy'] = True

        # Disable the 'Process' button, disable the context customization menu
        self.gbutton.config(state='disabled')
        self.context_menu.entryconfig('Customize Plugin', state='disabled')

        totals = 0
        self.clear_box()
        self.showCmdOutput('Starting...\n', tag='header')

        # Loop through the files selected in Sigil's Book View
        for (typ, ident) in self.bk.selected_iter():
            # Skip the ones that aren't the "Text" mimetype.
            if self.bk.id_to_mime(ident) != 'application/xhtml+xml':
                continue
            href = self.bk.id_to_href(ident)
            # Param 1 - the contents of the (x)html file.
            self.criteria['html'] = self.bk.readfile(ident)
            if not isinstance(self.criteria['html'], text_type):
                self.criteria['html'] = text_type(self.criteria['html'], 'utf-8')

            # Hand off the "criteria" parameters dictionary to the parsing engine
            parser = MarkupParser(self.criteria)

            # Retrieve the new markup and the number of occurrences changed
            try:
                html, occurrences = parser.processml()
            except:
                self.showCmdOutput('Error parsing %s! File skipped.\n' % href, 'error')
                continue

            # Report whether or not changes were made (and how many)
            totals += occurrences
            if occurrences:
                # write changed markup back to file
                self.bk.writefile(ident, html)
                self.showCmdOutput('Occurrences found/changed in %s: %d\n' % (href, occurrences), 'change')
            else:
                self.showCmdOutput('Criteria not found in %s\n' % href, 'nochange')

        # report totals
        if totals:
            self.qbutton.config(text='Commit & Exit')
            self.bbutton.config(state='normal')
            self.showCmdOutput('Total occurrences found/changed: %d\n' % totals, 'totals')
        else:
            self.showCmdOutput('No changes made to book\n', 'totals')
        self.showCmdOutput('Finished\n', tag='header')

    def copy_existing_chkbox_actions(self):
        '''Actions to be taken when Copy Existing is checked/unchecked'''
        if self.copy_attrs.get():
            self.attrStr_entry.delete(0, tkinter_constants.END)
            self.attrStr_entry.config(state='disabled')
        else:
            self.attrStr_entry.config(state='normal')

    def action_change_actions(self, event):
        '''Actions to be taken when action (modify/delete) combobox is changed'''
        if self.action_combo_value.get() == 'Delete':
            self.newtag_combo.current(0)
            self.newtag_combo.config(state='disabled')
            self.attrStr_entry.delete(0, tkinter_constants.END)
            self.attrStr_entry.config(state='disabled')
            self.copy_attrs_checkbox.deselect()
            self.copy_attrs_checkbox.config(state='disabled')
        else:
            self.newtag_combo.config(state='enabled')
            self.newtag_combo.current(0)
            self.attrStr_entry.config(state='normal')
            self.copy_attrs_checkbox.config(state='normal')

    def attribute_change_actions(self, event):
        '''Actions to be taken when attributes combobox is changed.'''
        if self.attrs_combo_value.get() == self.NO_ATTRIB_STR:
            self.attrvalue_entry.delete(0, tkinter_constants.END)
            self.attrvalue_entry.config(state='disabled')
            self.regex_checkbox.deselect()
            self.regex_checkbox.config(state='disabled')
        else:
            self.attrvalue_entry.config(state='normal')
            self.regex_checkbox.config(state='normal')

    def tag_change_actions(self, event):
        '''Actions to be taken when the "Tag" combobox is changed'''
        # (populates the New Tag combobox with suitable choices)
        self.newtag_combo['values'] = [self.NO_CHANGE_STR] + self.combobox_values['{}_changes'.format(self.tag_combo_value.get())]
        self.newtag_combo.current(0)

    def update_attrs_combo(self):
        '''refesh the attributes combobox'''
        self.attrs_combo['values'] = self.combobox_values['attrs'] + [self.NO_ATTRIB_STR]
        self.attrs_combo.current(0)

    def update_msgbox(self):
        '''Pop a tkinter info messagebox about available plugin update'''
        title = 'Plugin Update Available'
        msg = 'Version {} of the {} plugin is now available.'.format(self.newversion, self.bk._w.plugin_name)
        tkinter_msgbox.showinfo(title, msg)

    def check_for_update(self):
        '''Use updatecheck.py to check for newer versions of the plugin'''
        last_time_checked = self.update_prefs['last_time_checked']
        last_online_version = self.update_prefs['last_online_version']
        chk = UpdateChecker(last_time_checked, last_online_version, self.bk._w)
        update_available, online_version, time = chk.update_info()
        # update preferences with latest date/time/version
        self.update_prefs['last_time_checked'] = time
        if online_version is not None:
            self.update_prefs['last_online_version'] = online_version
        if update_available:
            return (True, online_version)
        return (False, online_version)

    def showConfig(self):
        ''' Launch Customization Dialog '''
        guiConfig(self, combobox_defaults, self.font_tweaks)

    def quitApp(self):
        '''Clean up and close Widget'''
        global prefs

        # preserve the three main gui selections
        self.misc_prefs['windowGeometry'] = self.parent.geometry()
        self.gui_prefs['action'] = self.action_combo.current()
        self.gui_prefs['tag'] = self.tag_combo.current()
        self.gui_prefs['attrs'] = self.attrs_combo.current()

        # copy preferences settings groups pack to global dict
        prefs['gui_selections'] = self.gui_prefs
        prefs['miscellaneous_settings'] = self.misc_prefs
        prefs['update_settings'] = self.update_prefs
        prefs['combobox_values'] = self.combobox_values

        self.parent.destroy()
        self.quit()

    def clear_box(self):
        '''Clear the scrolling textbox.'''
        self.results.delete(1.0, tkinter_constants.END)
        return

    def showCmdOutput(self, msg, tag='nochange'):
        '''Write messages to the scrolling textbox.'''
        normalFont = tkFont.Font(family=self.font_tweaks['font_family'], size=int(self.font_tweaks['font_size']), weight=tkFont.NORMAL)
        if int(self.font_tweaks['font_size']) < 0:
            boldBigFont = tkFont.Font(family=self.font_tweaks['font_family'], size=int(self.font_tweaks['font_size'])-1, weight=tkFont.BOLD)
        else:
            boldBigFont = tkFont.Font(family=self.font_tweaks['font_family'], size=int(self.font_tweaks['font_size'])+1, weight=tkFont.BOLD)
        boldFont = tkFont.Font(family=self.font_tweaks['font_family'], size=int(self.font_tweaks['font_size']), weight=tkFont.BOLD)
        summaryFont = tkFont.Font(family=self.font_tweaks['font_family'], size=int(self.font_tweaks['font_size']), weight=tkFont.BOLD, underline=True)

        self.results.tag_config('nochange', lmargin1=10, lmargin2=30, spacing1=3, font=normalFont)
        self.results.tag_config('header', spacing1=5, spacing3=5, font=boldBigFont)
        self.results.tag_config('totals', lmargin1=10, lmargin2=30, spacing1=5, font=summaryFont)
        self.results.tag_config('change', lmargin1=10, lmargin2=30, spacing1=3, foreground="blue", font=normalFont)
        self.results.tag_config('error', lmargin1=10, lmargin2=30, spacing1=3, foreground="red", font=boldFont)

        self.results.insert(tkinter_constants.END, msg, tag)
        self.results.yview_pickplace(tkinter_constants.END)
        return


def run(bk):
    # before Sigil 0.8.900 and plugin launcher 20150909, bk.selected_iter doesn't exist.
    if bk.launcher_version() < 20150909:
        print('Error: The %s plugin requires Sigil version 0.8.900 or higher.' % bk._w.plugin_name)
        return -1

    # Fail if no Text files are selected in Sigil's Book Browser
    count = 0
    for (typ, ident) in bk.selected_iter():
        if bk.id_to_mime(ident) == 'application/xhtml+xml':
            count += 1
    if not count:
        print('No text files selected in Book Browser!')
        return -1

    global prefs
    prefs = bk.getPrefs()

    if 'font_tweaks' not in prefs:
        prefs['font_tweaks'] = font_tweaks
    else: # otherwise, use the piecemeal method in case new prefs have been added since json creation.
        check_for_new_prefs(prefs['font_tweaks'], font_tweaks)
    if 'gui_selections' not in prefs:  # If the json doesn't exist yet, assign wholesale defaults.
        prefs['gui_selections'] = gui_selections
    else:
        check_for_new_prefs(prefs['gui_selections'], gui_selections)
    if 'miscellaneous_settings' not in prefs:
        prefs['miscellaneous_settings']= miscellaneous_settings
    else:
        check_for_new_prefs(prefs['miscellaneous_settings'], miscellaneous_settings)
    if 'update_settings' not in prefs:
        prefs['update_settings'] = update_settings
    else:
        check_for_new_prefs(prefs['update_settings'], update_settings)
    if 'combobox_values' not in prefs:
        prefs['combobox_values'] = combobox_defaults
    else:
        check_for_new_prefs(fix_old_keys(prefs['combobox_values']), combobox_defaults)

    root = tkinter.Tk()
    root.withdraw()
    root.title('')
    root.resizable(True, True)
    root.minsize(420, 325)
    default_font = tkFont.Font(family=prefs['font_tweaks']['font_family'], size=int(prefs['font_tweaks']['font_size']))
    root.option_add('*font', default_font)
    if not sys.platform.startswith('darwin'):
        img = tkinter.Image('photo', file=os.path.join(bk._w.plugin_dir, bk._w.plugin_name, 'images/icon.png'))
        root.tk.call('wm','iconphoto',root._w,img)
    guiMain(root, bk).pack(fill=tkinter_constants.BOTH)
    root.mainloop()

    # Save prefs to back to json
    bk.savePrefs(prefs)
    if BAIL_OUT:
        print('Changes aborted by user.\n')
        return -1
    return 0


def main():
    print('I reached main when I should not have\n')
    return -1


if __name__ == "__main__":
    sys.exit(main())
