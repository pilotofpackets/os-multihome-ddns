"""
Preview renderer: turns the plugin's .volt views + form XML into static HTML pages
wrapped in the OPNsense default layout, so they can be screenshotted with the real
theme, Tabulator grid wrapper and OPNsense JS. API calls are mocked by shoot.py.
"""
import html
import os
import re
import sys
import xml.etree.ElementTree as ET

PLUGIN = sys.argv[1]          # .../multihome-ddns/src/opnsense/mvc/app
OUT = sys.argv[2]             # .../preview/site/ui/multihomeddns
VIEWS = os.path.join(PLUGIN, 'views/OPNsense/MultihomeDDNS')
FORMS = os.path.join(PLUGIN, 'controllers/OPNsense/MultihomeDDNS/forms')

CSS = ['/ui/themes/opnsense/build/css/main.css', '/ui/css/bootstrap-select.css', '/ui/themes/opnsense/build/css/bootstrap-dialog.css',
       '/ui/css/tabulator.min.css', '/ui/themes/opnsense/build/css/opnsense-bootgrid.css', '/ui/css/opnsense-bootgrid-layout.css',
       '/ui/assets/fontawesome/css/all.min.css', '/ui/assets/fontawesome/css/v4-shims.min.css', '/ui/themes/opnsense/build/css/tokenize2.css']
JS = ['/ui/js/polyfills.js', '/ui/js/jquery-3.5.1.min.js', '/ui/js/tokenize2.js', '/ui/js/tabulator.min.js',
      '/ui/js/opnsense_bootgrid.js', '/ui/js/bootstrap3-typeahead.min.js', '/ui/js/opnsense.js', '/ui/js/opnsense_ui.js',
      '/ui/js/bootstrap.min.js', '/ui/js/bootstrap-select.min.js', '/ui/js/bootstrap-dialog.min.js']


def esc(s):
    return html.escape(s or '', quote=True)


def form_sections(name):
    root = ET.parse(os.path.join(FORMS, name + '.xml')).getroot()
    sections, current = [], {'type': None, 'label': None, 'children': []}
    for fld in root:
        f = {child.tag: (child.text or '').strip() for child in fld}
        if f.get('type') == 'header':
            if current['children'] or current['label']:
                sections.append(current)
            current = {'type': 'header', 'label': f.get('label'), 'children': []}
        else:
            current['children'].append(f)
    sections.append(current)
    return sections


def field_row(f):
    fid, typ, label, help_ = f.get('id'), f.get('type'), f.get('label'), f.get('help')
    icon = ('<a id="help_for_%s" href="#" class="showhelp"><i class="fa fa-info-circle fa-fw"></i></a>' % fid) if help_ \
        else '<i class="fa fa-info-circle fa-fw text-muted"></i>'
    adv = ' data-advanced="true"' if f.get('advanced') == 'true' else ''
    advicon = '<i class="fa fa-cog fa-sm fa-fw text-warning"></i>' if adv else ''
    if typ == 'text':
        ctrl = '<input type="text" class="form-control %s" size="50" id="%s">' % (esc(f.get('style')), fid)
    elif typ == 'password':
        ctrl = '<input type="password" autocomplete="new-password" class="form-control" size="50" id="%s">' % fid
    elif typ == 'checkbox':
        ctrl = '<input type="checkbox" class="%s" id="%s">' % (esc(f.get('style')), fid)
    elif typ in ('dropdown', 'select_multiple'):
        multi = ' multiple="multiple"' if typ == 'select_multiple' else ''
        style = f.get('style') or 'selectpicker'
        ctrl = ('<div id="select_%s"><select%s data-size="10" id="%s" class="%s" data-container="body" '
                'data-none-selected-text="Nothing selected" data-width="346px" data-allownew="false" '
                'data-live-search="true"></select>' % (fid, multi, fid, style))
        if typ == 'select_multiple':
            ctrl += ('&nbsp;&nbsp;<a href="#" class="text-danger" id="clear-options_%s"><i class="fa fa-times-circle"></i> '
                     '<small>Clear All</small></a>' % fid)
        ctrl += '</div>'
    else:
        ctrl = '<span id="%s"></span>' % fid
    helpdiv = '<div class="hidden" data-for="help_for_%s"><small>%s</small></div>' % (fid, esc(help_)) if help_ else ''
    return ('<tr id="row_%s"%s><td><div class="control-label" id="control_label_%s">%s <b>%s</b>%s</div></td>'
            '<td>%s%s</td><td><span class="help-block" id="help_block_%s"></span></td></tr>'
            % (fid, adv, fid, icon, esc(label), advicon, ctrl, helpdiv, fid))


def section_table(section, show_toggles, form_id, has_adv, has_help):
    out = ['<div class="table-responsive form-search-section">'
           '<table class="table table-striped table-condensed" style="table-layout: fixed; width: 100%;">'
           '<colgroup><col style="width: 25%;"/><col style="width: 40%;"/><col style="width: 35%;"/></colgroup>']
    if section['type']:
        out.append('<thead style="cursor: pointer;"><tr><th colspan="3"><div style="padding-bottom: 5px; padding-top: 5px; '
                   'font-size: 16px;"><i class="fa fa-angle-down" aria-hidden="true"></i> &nbsp; <b>%s</b></div></th></tr></thead>'
                   % esc(section['label']))
    out.append('<tbody class="collapsible">')
    if show_toggles and not section['type'] and (has_adv or has_help):
        out.append('<tr><td colspan="3"><span>%s</span><span class="pull-right">%s</span></td></tr>' % (
            ('<a href="#"><i class="fa fa-toggle-off fa-fw text-danger" id="show_advanced_%s"></i></a> <small>advanced mode</small>'
             % form_id) if has_adv else '',
            ('<i class="fa fa-info-circle fa-sm fa-fw text-primary"></i> <small>full help</small> <a href="#">'
             '<i class="fa fa-toggle-off fa-fw text-danger" id="show_all_help_%s"></i></a>' % form_id) if has_help else ''))
    for f in section['children']:
        out.append(field_row(f))
    out.append('</tbody></table></div>')
    return ''.join(out)


def flags(sections):
    fields = [f for s in sections for f in s['children']]
    return any(f.get('advanced') == 'true' for f in fields), any(f.get('help') for f in fields)


def base_form(form, form_id):
    sections = form_sections(form)
    adv, hlp = flags(sections)
    return '<form id="%s" class="form-inline">%s</form>' % (
        form_id, ''.join(section_table(s, True, form_id, adv, hlp) for s in sections))


def base_dialog(form, dialog_id, label):
    sections = form_sections(form)
    adv, hlp = flags(sections)
    tables = ''.join(section_table(s, True, 'frm_' + dialog_id, adv, hlp) for s in sections)
    return ('<div class="modal fade" id="%s" tabindex="-1" role="dialog"><div class="modal-backdrop fade in"></div>'
            '<div class="modal-dialog modal-lg"><div class="modal-content"><div class="modal-header">'
            '<button type="button" class="close" data-dismiss="modal"><span aria-hidden="true">&times;</span></button>'
            '<div class="input-group form-search pull-right" style="width: 250px; margin-top: -6px; margin-right: 15px;">'
            '<span class="input-group-addon"><i class="fa fa-search"></i></span><input type="search" class="form-control" '
            'placeholder="Search form"></div><h4 class="modal-title">%s</h4></div><div class="modal-body"><form id="frm_%s">%s'
            '</form></div><div class="modal-footer"><button type="button" class="btn btn-default" data-dismiss="modal">Cancel'
            '</button><button type="button" class="btn btn-primary" id="btn_%s_save">Save <i id="btn_%s_save_progress"></i>'
            '</button></div></div></div></div>' % (dialog_id, esc(label), dialog_id, tables, dialog_id, dialog_id))


def render_volt(name, title):
    src = open(os.path.join(VIEWS, name + '.volt')).read()
    src = re.sub(r'\{#.*?#\}', '', src, flags=re.S)
    common = re.sub(r'\{#.*?#\}', '', open(os.path.join(VIEWS, 'common.volt')).read(), flags=re.S)
    src = re.sub(r"\{\{\s*partial\('OPNsense/MultihomeDDNS/common'\)\s*\}\}", lambda m: common, src)

    def partial(m):
        args = m.group(2)
        fields = re.search(r"'fields':(\w+)", args).group(1)
        ident = re.search(r"'id':'([^']+)'", args).group(1)
        form = {'formGeneral': 'general', 'formDialogAccount': 'dialogAccount', 'formDialogFailover': 'dialogFailover'}[fields]
        if m.group(1) == 'base_form':
            return base_form(form, ident)
        label = re.search(r"'label':lang\._\('([^']+)'\)", args).group(1)
        return base_dialog(form, ident, label)
    src = re.sub(r'\{\{\s*partial\("layout_partials/(base_form|base_dialog)",\s*\[(.*?)\]\s*\)\s*\}\}', partial, src, flags=re.S)
    src = re.sub(r"\{\{\s*lang\._\('((?:[^'\\]|\\.)*)'\)\s*\}\}", lambda m: m.group(1), src)
    leftover = re.findall(r'\{\{.*?\}\}|\{%.*?%\}', src)
    if leftover:
        print('WARN unrendered volt in %s: %s' % (name, leftover[:3]))
    head = ''.join('<link href="%s" rel="stylesheet">' % c for c in CSS) + ''.join('<script src="%s"></script>' % j for j in JS)
    page = ('<!doctype html><html lang="de" class="no-js"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1, minimum-scale=1"><title>%s</title>%s</head><body>'
            '<header class="page-head"><nav class="navbar navbar-default"><div class="container-fluid"><div class="navbar-header">'
            '<a class="navbar-brand" href="#"><img class="brand-logo" src="/ui/themes/opnsense/build/images/default-logo.svg" height="30"></a>'
            '</div></div></nav></header>'
            '<main class="page-content col-sm-12"><div class="row"><header class="page-content-head"><div class="container-fluid">'
            '<ul class="list-inline"><li><h1>%s</h1></li></ul></div></header><section class="page-content-main">'
            '<div class="container-fluid"><div class="row"><section class="col-xs-12"><div id="messageregion"></div>%s'
            '</section></div></div></section></div></main></body></html>') % (esc(title), head, esc(title), src)
    os.makedirs(OUT, exist_ok=True)
    open(os.path.join(OUT, name + '.html'), 'w').write(page)


render_volt('index', 'Services: Multihome DynDNS: Einträge')
render_volt('failover', 'Services: Multihome DynDNS: Failover-DNS')
render_volt('general', 'Services: Multihome DynDNS: Einstellungen')
print('rendered')
