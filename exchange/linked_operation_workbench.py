"""Mount restricted linked operations on the existing server, not another host."""
from html import escape
import json
import secrets
from urllib.parse import parse_qs, urlsplit
from .linked_operation_controller import LinkedOperationController
from .linked_operation_locales import WORDS, ORDER, TASK_LABELS, RECOVERY_LABELS, RECOVERY_CONFIRM_LABELS, ASSET_RETURN_CONFIRM_LABELS, ECONOMIC_LABELS


def mount_linked_operations(server, controller):
    if type(controller) is not LinkedOperationController:
        raise ValueError('original linked controller required')
    previous = server.RequestHandlerClass
    def refresh_original_view():
        from .exchange_fact_rehydration import rehydrate_exchange_facts
        row, _ = controller.linked.runtime.checkpoint.read()
        restored = rehydrate_exchange_facts(row['components']['owned-facts'],
                                            controller.mapping.fresh_runtime(row))
        access = server.binding._access
        with access._lock:
            access._exchange = restored._exchange
        # All directory bindings were created by the same original access.
        # This changes no persisted bytes and grants no command authority.
        return row
    server.linked_operations = controller

    class LinkedHandler(previous):
        @staticmethod
        def native_navigation(locale):
            if locale not in WORDS:
                raise ValueError('supported original locale required')
            return previous.native_navigation(locale) + '<nav><a href="/linked-operation?lang='+locale+'">'+escape(WORDS[locale][0])+'</a></nav>'

        def do_GET(self):
            if not self.host_ok():
                return self.send_body(403, 'Original host required')
            try:
                controller._guard(self, 'view')
                refresh_original_view()
            except PermissionError:
                return self.send_body(403, 'Original caller authorization unavailable')
            except Exception:
                return self.send_body(503, 'Original linked state unavailable')
            parsed = urlsplit(self.path)
            if parsed.path != '/linked-operation':
                return super().do_GET()
            if len(parsed.query) > 64:
                return self.send_body(400, 'Invalid locale')
            query = parse_qs(parsed.query, keep_blank_values=True)
            locale = query.get('lang', ['en'])[0]
            if (parsed.fragment or not self.host_ok() or set(query) - {'lang'}
                    or any(len(v) != 1 for v in query.values()) or locale not in WORDS):
                return self.send_body(400, 'Invalid linked request')
            try:
                controller._guard(self, 'view')
                row, _ = controller.linked.runtime.checkpoint.read()
                # IDs identify original records; no owner/holder address or
                # private task mapping is enumerated by this page.
                words = WORDS[locale]
                forms = []
                actions = ORDER + (('task-prepare','task-reconcile','task-review','task-reserve') if controller.task_preparation is not None else ())
                labels = words[6] + (TASK_LABELS[locale] if controller.task_preparation is not None else ())
                if controller.recovery_workflow is not None:
                    actions += ('recovery-view',)
                    labels += (RECOVERY_LABELS[locale],)
                    recovery_view = controller.recovery_workflow.view(row['generation'])
                    if (controller.linked.execution_mode == 'native-enabled' and
                            (recovery_view['canConfirmExistingRefund'] or recovery_view['canConfirmExistingAssetReturn'])):
                        actions += ('recovery-confirm',)
                        labels += ((ASSET_RETURN_CONFIRM_LABELS if recovery_view['canConfirmExistingAssetReturn'] else RECOVERY_CONFIRM_LABELS)[locale],)
                if controller.economic_verifier is not None:
                    actions += ('economic-observe',) + (('economic-confirm',) if controller.economic_verifier.bound else ())
                    labels += ECONOMIC_LABELS[locale][:2 if controller.economic_verifier.bound else 1]
                for index, action in enumerate(actions):
                    inputs = ('operation',) if action in ('review','observe','dispatch') else (
                        ('request','logIndex','version') if action == 'oracle-observe' else ('obligation',))
                    if action.startswith('economic-'):
                        inputs = ('operation',)
                    if action.startswith('recovery-'):
                        inputs = ()
                    if action.startswith('task-'):
                        inputs = ('proposal',)
                    fields = ''.join('<label>'+escape(name)+'<input name="'+name+'" required maxlength="128"></label>' for name in inputs)
                    if action == 'dispatch':
                        fields += ('<label><input type="checkbox" name="confirm" '
                                   'value="dispatch-existing-prepared-operation" required>'
                                   +escape(words[5])+'</label>')
                    forms.append('<form method="post" action="/linked-operation">'
                        '<input type="hidden" name="csrf" value="'+escape(self.server.csrf,quote=True)+'">'
                        '<input type="hidden" name="action" value="'+action+'">'
                        '<input type="hidden" name="lang" value="'+locale+'">'
                        '<input type="hidden" name="generation" value="'+str(row['generation'])+'">'
                        +fields+'<button>'+escape(labels[index])+'</button></form>')
                nav = ' '.join('<a href="/linked-operation?lang='+key+'">'+key+'</a>' for key in WORDS)
                self.send_body(200, '<!doctype html><html lang="'+locale+'"><meta charset="utf-8">'
                    '<title>'+escape(words[0])+'</title><main><h1>'+escape(words[0])+'</h1><nav>'+nav+'</nav>'
                    '<p>'+escape(words[1])+'</p><p>'+escape(words[2])+': '+str(row['generation'])+'</p>'
                    +''.join(forms)+'</main></html>')
            except PermissionError:
                self.send_body(403, 'Original caller authorization unavailable')
            except Exception:
                self.send_body(503, 'Original linked state unavailable')

        def do_POST(self):
            parsed = urlsplit(self.path)
            if parsed.path != '/linked-operation':
                return self.send_body(403, 'Use explicitly bound linked actions; legacy writes unavailable')
            if parsed.query or parsed.fragment or not self.host_ok() or self.headers.get('Origin') != self.server.origin:
                return self.send_body(403, 'Original origin required')
            try:
                if self.headers.get('Content-Type') != 'application/x-www-form-urlencoded':
                    raise ValueError('content type')
                size = int(self.headers.get('Content-Length','0'))
                if not 0 < size <= 2048:
                    raise ValueError('size')
                form = parse_qs(self.rfile.read(size).decode('utf-8'), strict_parsing=True,
                                keep_blank_values=True, max_num_fields=8)
                if any(len(value)!=1 for value in form.values()):
                    raise ValueError('duplicate fields')
                values = {key:value[0] for key,value in form.items()}
                token = values.pop('csrf', '')
                if not token.isascii() or not secrets.compare_digest(token,self.server.csrf):
                    return self.send_body(403, 'Original CSRF required')
                locale = values.pop('lang', 'en')
                if locale not in WORDS:
                    raise ValueError('locale')
                words = WORDS[locale]
                action = values.pop('action')
                generation = values.get('generation','')
                if not generation.isascii() or not generation.isdecimal() or not 0 < int(generation) < 2**63:
                    raise ValueError('generation')
                values['generation'] = int(generation)
                result = controller.execute(self,action,values)
                # The controller only returns sanitized public status/locator.
                body = '<pre>'+escape(json.dumps(result,sort_keys=True))+'</pre>'
                if action in ('review','task-review'):
                    body += '<a rel="noopener noreferrer" href="'+escape(result['url'],quote=True)+'">'+escape(words[3])+'</a>'
                self.send_body(200, '<!doctype html><html lang="'+locale+'"><title>'+escape(words[0])+'</title>'+body+
                               '<a href="/linked-operation?lang='+locale+'">'+escape(words[4])+'</a></html>')
            except PermissionError:
                self.send_body(403, 'Original caller authorization unavailable')
            except Exception:
                # Do not expose private proof, task addresses or provider data.
                # An uncertain side effect is never advertised as retryable.
                self.send_body(409, 'Unavailable or changed. Reconcile original state; do not replay.')
    server.RequestHandlerClass = LinkedHandler
    return server
