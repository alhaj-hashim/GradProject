from odoo import api, fields, models
from odoo.exceptions import except_orm, Warning ,UserError, ValidationError

class RejectLeavesByManager(models.TransientModel):
    _name = 'dms.rjct.lev.wiz'

    note = fields.Text('Reason', required=True)


    @api.multi
    def reject_leave(self):
        context = dict(self._context or {})
        active_ids = context.get('active_ids', []) or []

        # print('active ids : ', active_ids)
        for rec in self.env['hr.leave'].browse(active_ids):
            if rec.state == 'dirmang':
                rec.write({'note_dm' : self.note})

            if rec.state == 'validate1':
                rec.write({'note_hm' : self.note})

            rec.action_reject()
        return {'type': 'ir.actions.act_window_close'}
