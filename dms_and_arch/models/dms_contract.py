import base64

from odoo import models, fields, api, _

class dmsHrContract(models.Model):
    _inherit = 'hr.contract'

    state = fields.Selection([
        ('draft', 'Draft'),
        ('accounted', 'In Accounted'),
        ('hrmang', 'In HR Manager'),
        ('approved', 'Awaiting Signature'),
        ('pending', 'To Renew'),
        ('open', 'Running'),
        ('close', 'Expire'),
        ('cancel', 'Canceled')
    ], string='Status', readonly=True, track_visibility='onchange', copy=False, defualt='draft')
    wage = fields.Monetary('Wage', digits=(16, 2), track_visibility="onchange",
                           help="Employee's monthly gross wage.")
    pdf_contract = fields.Binary('PDF Contract')

    # Document Archive
    def _generate_name_to_pdf(self):
        res = ""
        for contract in self:
            res += (_("%(emp_name)s 's - Contract.pdf") %{
                'emp_name': contract.employee_id.name
            })
        return res

    def _generate_pdf(self):

        pdf = self.env.ref('dms_and_arch.action_hr_contract_report').sudo().render_qweb_pdf([self.id])[0]
        pdf_contract = base64.b64encode(pdf)

        muk_dms = self.env['muk_dms.file']
        muk_dms_directory = self.env['muk_dms.directory']
        directory_id = muk_dms_directory.search([('name', 'like', 'Temp')], limit=1)

        res = muk_dms.create({
            'content': pdf_contract,
            'directory': directory_id.id,
            'name': self._generate_name_to_pdf()
        })

        return res

    def open_muk_directory(self):
        self._generate_pdf()
        ir_model_data = self.env['ir.model.data']
        try:
            muk_tree_id = ir_model_data.get_object_reference('muk_dms', 'view_dms_file_tree')[1]
        except ValueError:
            muk_tree_id = False
        domain = [('directory.name', 'ilike', 'Temp')]
        return {
            'type': 'ir.actions.act_window',
            'name': _('Archived Documents'),
            'view_type': 'tree',
            'view_mode': 'tree',
            'res_model': 'muk_dms.file',
            'views': [
                (muk_tree_id, 'tree'),
                (False, 'form')
            ],
            'view_id': muk_tree_id,
            'target': 'current',
            'domain': domain
        }

    @api.multi
    def action_to_acc(self):
        self.state = 'accounted'
        return True

    @api.multi
    def action_to_approve(self):
        self.state = 'approved'
        return True

    @api.multi
    def contract_open(self):
        self.state = 'open'
        return True

