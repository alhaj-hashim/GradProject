import base64

from odoo import models, fields, api, _
from odoo.exceptions import except_orm, Warning ,UserError, ValidationError

from odoo12.odoo.exceptions import AccessError


class dmsHRleave(models.Model):
    _inherit = 'hr.leave'

    holiday_status_id = fields.Many2one(
        "hr.leave.type", string="Leave Type", required=True, readonly=True,
        states={'draft': [('readonly', False)], 'dirmang': [('readonly', False)]},
        domain=[('valid', '=', True)])
    state = fields.Selection([
        ('draft', 'New'),
        ('cancel', 'Cancelled'),
        ('dirmang', 'Direct Manager'),
        ('refuse', 'Reject'),
        ('confirm', 'HR Employee'),
        ('validate1', 'HR Manager'),
        ('validate', 'Approved')
    ], string='Status', readonly=True, track_visibility='onchange', copy=False, default='dirmang')
    note_dm = fields.Text('Direct Manager', readonly=True)
    note_hm = fields.Text('HR Manager', readonly=True)

    @api.multi
    def action_to_dm(self):
        self.state = 'dirmang'
        return True

    @api.multi
    def action_to_hremp(self):
        current_employee = self.env['hr.employee'].search([('user_id', '=', self.env.uid)], limit=1)
        self.state = 'confirm'
        self.write({'first_approver_id': current_employee.id})
        return True

    @api.multi
    def action_to_hrmang(self):
        self.state = 'validate1'
        return True

    @api.multi
    def action_reject(self):
        current_employee = self.env['hr.employee'].search([('user_id', '=', self.env.uid)], limit=1)
        if any(holiday.state not in ['dirmang', 'validate1'] for holiday in self):
            raise UserError(_('Leave request refused just by Direct Manager or HR Manager.'))

        validated_holidays = self.filtered(lambda hol: hol.state == 'dirmang' or hol.state == 'validate1')
        validated_holidays.write({'state': 'refuse', 'first_approver_id': current_employee.id})
        (self - validated_holidays).write({'state': 'refuse', 'second_approver_id': current_employee.id})
        # Delete the meeting
        self.mapped('meeting_id').unlink()
        # If a category that created several holidays, cancel all related
        linked_requests = self.mapped('linked_request_ids')
        if linked_requests:
            linked_requests.action_refuse()
        self._remove_resource_leave()
        self.activity_update()
        return True

    @api.multi
    def reset_to_draft(self):
        if any(holiday.state not in 'dirmang' for holiday in self):
            raise UserError(_('Leave request state must be "Direct Manager" in order to be reset to draft.'))
        self.write({
            'state': 'draft',
            'first_approver_id': False,
            'second_approver_id': False,
            'note_dm' : False,
            'note_hm' : False
        })
        linked_requests = self.mapped('linked_request_ids')
        if linked_requests:
            linked_requests.action_draft()
            linked_requests.unlink()
        self.activity_update()
        return True

    @api.multi
    @api.depends('state', 'employee_id', 'department_id')
    def _compute_can_reset(self):
        res = super(dmsHRleave, self)._compute_can_reset()
        for holiday in self:
            try:
                holiday._check_approval_update('draft')
            except (AccessError, UserError):
                holiday.can_reset = False
            else:
                holiday.can_reset = True
        return res

    @api.depends('state', 'employee_id', 'department_id')
    def _compute_can_approve(self):
        res = super(dmsHRleave, self)._compute_can_approve()
        for holiday in self:
            try:
                if holiday.state == 'confirm' :
                    holiday._check_approval_update('validate1')
                else:
                    holiday._check_approval_update('validate')
            except (AccessError, UserError):
                holiday.can_approve = False
            else:
                holiday.can_approve = True
        return res

    #Override _check_approval_update  method
    def _check_approval_update(self, state):
        """ Check if target state is achievable. """
        current_employee = self.env['hr.employee'].search([('user_id', '=', self.env.uid)], limit=1)

        is_dep_mngr = self.env.user.has_group('dms_and_arch.group_dms_depmanagr')
        is_hr_emp = self.env.user.has_group('dms_and_arch.group_dms_hremp')
        is_hr_mngr = self.env.user.has_group('dms_and_arch.group_dms_hrmanagr')

        for holiday in self:
            if state == 'dirmang':
                continue

            if state == 'draft':
                if holiday.employee_id != current_employee and not is_dep_mngr:
                    raise UserError(_('Only a Department manager can reset other people leaves.'))
                continue

            if state == 'validate1':
                if not is_hr_emp:
                    raise UserError(_('Only an HR Employee can Validate leave requests to HR Manager.'))

            if is_dep_mngr:
                # use ir.rule based first access check: department, members, ... (see security.xml)
                holiday.check_access_rule('write')

            if is_hr_emp:
                # use ir.rule based first access check: department, members, ... (see security.xml)
                holiday.check_access_rule('write')

            if state == 'validate':
                if not is_hr_mngr:
                    raise UserError(_('Only an HR Manager can apply the second approval on leave requests.'))

    # Document Archive
    def _generate_name_to_pdf(self):
        res = ""
        for leave in self:
            res += (_("%(emp_name)s  - (%(hol_status)s).pdf") % {
                'emp_name': leave.employee_id.name,
                'hol_status': leave.holiday_status_id.name
            })
        return res

    def _generate_pdf(self):

        pdf = self.env.ref('dms_and_arch.action_leave_req_report').sudo().render_qweb_pdf([self.id])[0]
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

    # @api.multi
    # def action_validate(self):
    #     res = super(dmsHRleave, self).action_validate()
    #
    #     current_employee = self.env['hr.employee'].search([('user_id', '=', self.env.uid)], limit=1)
    #     is_hr_mngr = current_employee.has_group('dms_and_arch.group_dms_hrmanagr')
    #     if any(holiday.state not in 'validate1' for holiday in self):
    #         raise UserError(_('Leave request must be confirmed in order to approve it.'))
    #
    #     if not is_hr_mngr:
    #         raise UserError(_('You must be HR Manager to approve it.'))
    #
    #     if is_hr_mngr:
    #         self.write({
    #             'state': 'validate',
    #             'second_approver_id': current_employee.id})
    #
    #     for holiday in self.filtered(lambda holiday: holiday.holiday_type != 'employee'):
    #         if holiday.holiday_type == 'category':
    #             employees = holiday.category_id.employee_ids
    #         elif holiday.holiday_type == 'company':
    #             employees = self.env['hr.employee'].search([('company_id', '=', holiday.mode_company_id.id)])
    #         else:
    #             employees = holiday.department_id.member_ids
    #
    #         if self.env['hr.leave'].search_count([('date_from', '<=', holiday.date_to), ('date_to', '>', holiday.date_from),
    #                            ('state', 'not in', ['cancel', 'refuse']), ('holiday_type', '=', 'employee'),
    #                            ('employee_id', 'in', employees.ids)]):
    #             raise ValidationError(_('You can not have 2 leaves that overlaps on the same day.'))
    #
    #         values = [holiday._prepare_holiday_values(employee) for employee in employees]
    #         leaves = self.env['hr.leave'].with_context(
    #             tracking_disable=True,
    #             mail_activity_automation_skip=True,
    #             leave_fast_create=True,
    #         ).create(values)
    #         # leaves.action_approve()
    #         # FIXME RLi: This does not make sense, only the parent should be in validation_type both
    #         if leaves and leaves[0].validation_type == 'both':
    #             leaves.action_validate()
    #
    #     employee_requests = self.filtered(lambda hol: hol.holiday_type == 'employee')
    #     employee_requests._validate_leave_request()
    #     if not self.env.context.get('leave_fast_create'):
    #         employee_requests.activity_update()
    #     return res



class dmsHrEmployee(models.Model):
    _inherit = 'hr.employee'

    current_leave_state = fields.Selection(compute='_compute_leave_status', string="Current Leave Status",
                                           selection=[
                                               ('draft', 'New'),
                                               ('confirm', 'In HR Department'),
                                               ('dirmang', 'Waiting Direct Manager Approval'),
                                               ('refuse', 'Rejected'),
                                               ('validate1', 'Waiting HR Manager Approval'),
                                               ('validate', 'Approved'),
                                               ('cancel', 'Cancelled')
                                           ])
    # drmanager = fields.Boolean("Direct Manager")
    # hrmanager = fields.Boolean("HR Manager")
    emp_info = fields.Char("Employee Information", compute="_set_emp_info" , readonly=True)
    # drmanager_id = fields.Many2one('hr.employee', 'Direct Manager')

    @api.constrains('parent_id')
    def _check_parent_id(self):
        return True

    @api.multi
    def _set_emp_info(self):
        info = ""
        manager = self.department_id.manager_id.id
        for emp in self:
            if emp.id == manager:
                info += emp.name
                info += " is a "
                info += emp.department_id.name or ""
                info += " Manager"

                emp.emp_info = info
        return info


class dmsHrDepartment(models.Model):
    _inherit = 'hr.department'

    @api.multi
    def write(self, vals):
        """ If updating manager of a department, we need to update all the employees
            of department hierarchy, and subscribe the new manager.
        """
        # TDE note: auto-subscription of manager done by hand, because currently
        # the tracking allows to track+subscribe fields linked to a res.user record
        # An update of the limited behavior should come, but not currently done.
        if 'manager_id' in vals:
            manager_id = vals.get("manager_id")
            if manager_id:
                manager = self.env['hr.employee'].browse(manager_id)
                # subscribe the manager user
                if manager.user_id:
                    self.message_subscribe(partner_ids=manager.user_id.partner_id.ids)

            self._change_manager_department(manager_id)
            # set the employees's parent to the new manager
            self._update_employee_manager(manager_id)
        return super(dmsHrDepartment, self).write(vals)

    def _change_manager_department(self, manager_id):
        employees = self.env['hr.employee']
        for department in self:
            employees = employees | self.env['hr.employee'].search([
                ('id', '=', manager_id)
            ])
        employees.write({
            'department_id': department.id,
            'parent_id' : manager_id,
            'job_id' : '',
            'job_title' : ''
        })

