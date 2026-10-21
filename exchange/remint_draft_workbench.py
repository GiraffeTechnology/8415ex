"""Unsigned bill-term editing on the original serialized native workbench."""
from copy import deepcopy
from html import escape
import re
import secrets
from urllib.parse import parse_qs, urlsplit

from .demo_ui import MAX_BODY
from .errors import DomainError
from .mint_specification import MintSpecification
from .remint_draft_edit import edit_remint_draft
from .remint_review_workbench import RemintReviewWorkbenchServer, RemintReviewWorkbenchHandler
from .serialized_exchange_access import SerializedExchangeAccess


WORDS = {
    "en": ("Edit replacement bill terms", "Original bill terms", "Proposed complete terms",
        "Preview unsigned draft", "Unsigned draft preview", "The original terms remain unchanged. This editor does not sign, submit, burn or mint.",
        "Terms unavailable", "Draft request refused"),
    "zh-Hans": ("编辑换铸提单条款", "原提单条款", "拟新完整条款", "预览未签署草稿", "未签署草稿预览",
        "原条款保持不变。本编辑器不签署、不提交、不销毁或铸造。", "条款暂不可用", "草稿请求被拒绝"),
    "zh-Hant": ("編輯換鑄提單條款", "原提單條款", "擬新完整條款", "預覽未簽署草稿", "未簽署草稿預覽",
        "原條款保持不變。本編輯器不簽署、不提交、不銷毀或鑄造。", "條款暫不可用", "草稿請求被拒絕"),
    "fr": ("Modifier les conditions du connaissement de remplacement", "Conditions originales", "Conditions intégrales proposées",
        "Aperçu du brouillon non signé", "Brouillon non signé", "Les conditions originales restent inchangées. Cet éditeur ne signe, ne soumet, ne détruit et ne crée aucun NFT.",
        "Conditions indisponibles", "Demande de brouillon refusée"),
    "es": ("Editar las condiciones del conocimiento de reemplazo", "Condiciones originales", "Condiciones completas propuestas",
        "Vista previa del borrador sin firmar", "Borrador sin firmar", "Las condiciones originales no cambian. Este editor no firma, envía, destruye ni acuña.",
        "Condiciones no disponibles", "Solicitud de borrador rechazada"),
    "ja": ("再発行する船荷証券の条件を編集", "元の条件", "提案する条件の全文", "未署名の下書きを確認", "未署名の下書き",
        "元の条件は変更されません。この編集画面では署名、送信、焼却、発行を行いません。", "条件を取得できません", "下書きのリクエストを拒否しました"),
}


CURRENCY_WORDS = {
    "en": ("Allowed price currencies for the new NFT", "Original allowed currencies", "Select one or more original currency choices."),
    "zh-Hans": ("新NFT允许的计价币种", "原允许计价币种", "选择一个或多个原币种选项。"),
    "zh-Hant": ("新NFT允許的計價幣種", "原允許計價幣種", "選擇一個或多個原幣種選項。"),
    "fr": ("Devises de prix autorisées du nouveau NFT", "Devises autorisées originales", "Sélectionnez une ou plusieurs devises proposées."),
    "es": ("Monedas de precio permitidas del nuevo NFT", "Monedas permitidas originales", "Seleccione una o más monedas propuestas."),
    "ja": ("新しいNFTで許可する価格通貨", "元の許可通貨", "元の候補から1つ以上の通貨を選択してください。"),
}


def _currency_choices(value):
    if (type(value) is not tuple or not 1 <= len(value) <= 32
            or any(type(code) is not str or (re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", code) is None
                   or re.search(r"0x[0-9a-fA-F]{40}", code))
                   for code in value)
            or len(set(value)) != len(value)):
        raise ValueError("bounded unique original public currency codes required")
    return value


BUSINESS_FIELDS = ("commodityName", "commodityQuantity", "commodityUnit", "receiptNumber",
    "billNumber", "issuer", "registrar", "storageLocation", "tradeStopAt",
    "registrationDeadline", "registrationComparison")
BUSINESS_LABELS = {
    "en": ("Commodity", "Goods quantity", "Goods unit", "Receipt number", "Bill of lading number",
        "Issuer", "Registrar", "Storage location", "Trading cutoff (UTC Unix seconds)",
        "Registration deadline (UTC Unix seconds)", "Registration comparison"),
    "zh-Hans": ("商品", "商品数量", "商品单位", "收据编号", "提单编号", "签发人", "登记方", "存储地点",
        "交易截止（UTC Unix秒）", "登记截止（UTC Unix秒）", "登记比较语义"),
    "zh-Hant": ("商品", "商品數量", "商品單位", "收據編號", "提單編號", "簽發人", "登記方", "儲存地點",
        "交易截止（UTC Unix秒）", "登記截止（UTC Unix秒）", "登記比較語義"),
    "fr": ("Marchandise", "Quantité de marchandises", "Unité", "Numéro du reçu", "Numéro du connaissement",
        "Émetteur", "Registraire", "Lieu de stockage", "Fin de négociation (secondes Unix UTC)",
        "Échéance d'enregistrement (secondes Unix UTC)", "Comparaison d'enregistrement"),
    "es": ("Mercancía", "Cantidad de mercancía", "Unidad", "Número de recibo", "Número del conocimiento",
        "Emisor", "Registrador", "Lugar de almacenamiento", "Límite de negociación (segundos Unix UTC)",
        "Plazo de registro (segundos Unix UTC)", "Comparación de registro"),
    "ja": ("商品", "商品数量", "商品単位", "受領書番号", "船荷証券番号", "発行者", "登録者", "保管場所",
        "取引期限（UTC Unix秒）", "登録期限（UTC Unix秒）", "登録の比較条件"),
}


def _business_values(specification):
    receipt = specification.receipt
    values = (receipt.commodity_name, str(receipt.commodity_quantity), receipt.commodity_unit,
        receipt.receipt_number, specification.bill_of_lading_number, specification.issuer,
        specification.registrar, specification.storage_location, str(receipt.trade_stop_at),
        str(specification.registration_deadline), specification.registration_comparison)
    return dict(zip(BUSINESS_FIELDS, (_business_text(value) for value in values)))


def _business_updates(fields):
    if (type(fields) is not dict or set(fields) != set(BUSINESS_FIELDS)
            or any(type(value) is not str for value in fields.values())):
        raise ValueError("complete original public business fields required")
    values = {key: _business_text(value) for key, value in fields.items()}
    for key in ("commodityQuantity", "tradeStopAt", "registrationDeadline"):
        if re.fullmatch(r"0|[1-9][0-9]{0,77}", values[key]) is None:
            raise ValueError("canonical bounded integer business value required")
        values[key] = int(values[key])
        if values[key] >= 2 ** 256:
            raise ValueError("bounded integer business value required")
    return {
        "receipt": {"commodity_name": values["commodityName"],
            "commodity_quantity": values["commodityQuantity"], "commodity_unit": values["commodityUnit"],
            "receipt_number": values["receiptNumber"], "trade_stop_at": values["tradeStopAt"]},
        "specification": {"bill_of_lading_number": values["billNumber"], "issuer": values["issuer"],
            "registrar": values["registrar"], "storage_location": values["storageLocation"],
            "registration_deadline": values["registrationDeadline"],
            "registration_comparison": values["registrationComparison"]},
    }


ATTRIBUTE_WORDS = {
    "en": ("Proposed commodity attributes", "Original commodity attributes",
        "An empty optional value removes that attribute from the new draft."),
    "zh-Hans": ("拟新商品属性", "原商品属性", "可选值留空会从新草稿中删除该属性。"),
    "zh-Hant": ("擬新商品屬性", "原商品屬性", "可選值留空會從新草稿中刪除該屬性。"),
    "fr": ("Attributs proposés de la marchandise", "Attributs originaux",
        "Une valeur facultative vide supprime cet attribut du nouveau brouillon."),
    "es": ("Atributos propuestos de la mercancía", "Atributos originales",
        "Un valor opcional vacío elimina ese atributo del nuevo borrador."),
    "ja": ("提案する商品属性", "元の商品属性", "任意項目を空にすると新しい下書きから削除されます。"),
}


def _attribute_schema(specification):
    names = specification.template.applicable_fields
    if (type(names) is not tuple or len(names) > 64
            or any(_business_text(name) != name for name in names)):
        raise ValueError("bounded original public attribute schema required")
    return names


def _attribute_values(specification):
    return { _business_text(name): _business_text(value)
             for name, value in specification.public_attributes }


def _attribute_updates(seed, fields):
    names = _attribute_schema(seed)
    if (type(fields) is not dict
            or set(fields) != {"attribute." + str(i) for i in range(len(names))}
            or any(type(value) is not str for value in fields.values())):
        raise ValueError("complete original attribute fields required")
    values = {}
    for i, name in enumerate(names):
        value = fields["attribute." + str(i)]
        if value != "":
            values[name] = _business_text(value)
    # Keep the original seed's surviving order; append newly populated fields
    # in the original template order. No schema is selected by the request.
    ordered = [name for name, _ in seed.public_attributes if name in values]
    ordered += [name for name in names if name in values and name not in ordered]
    return tuple((name, values[name]) for name in ordered)


class RemintDraftUnavailable(ValueError):
    pass


def _business_text(value):
    if (type(value) is not str or not value.strip() or len(value) > 16384
            or re.search(r"0x[0-9a-fA-F]{40}", value)
            or any(ord(char) < 32 and char not in "\n\r\t" for char in value)):
        raise ValueError("bounded identity-excluding business text required")
    return value


class RemintDraftEditorBinding:
    """Trusted host supplies original typed declarations and nonsecret bill terms.

    No request selects a receipt, source reader, replacement asset or account.
    This is an unsigned editing aid, not an authorization or qualification gate.
    """
    def __init__(self, access, receipt_id, read_original_specifications, *,
                 read_currency_choices=None):
        if type(access) is not SerializedExchangeAccess or not callable(read_original_specifications):
            raise ValueError("original serialized access and declaration reader required")
        if read_currency_choices is not None and not callable(read_currency_choices):
            raise ValueError("original currency choices reader required when supplied")
        self.read_currency_choices = read_currency_choices
        self.access = access
        self.receipt_id = receipt_id
        self.read_original_specifications = read_original_specifications

    def draft(self, bill_terms=None, allowed_currencies=None, business_fields=None, attribute_fields=None):
        with self.access._lock:
            try:
                pair = deepcopy(self.read_original_specifications(self.receipt_id))
                if (type(pair) is not tuple or len(pair) != 2
                        or any(type(item) is not MintSpecification for item in pair)
                        or pair[0].receipt.receipt_id != self.receipt_id):
                    raise RemintDraftUnavailable("original bound declaration pair required")
                old, seed = pair
                old_text = _business_text(old.bill_terms)
                seed_text = _business_text(seed.bill_terms)
                old_fields = _business_values(old)
                _business_values(seed)
                attribute_names = _attribute_schema(seed)
                old_attributes = _attribute_values(old)
                _attribute_values(seed)
                choices = (None if self.read_currency_choices is None else
                           _currency_choices(deepcopy(self.read_currency_choices(self.receipt_id))))
                if choices is not None:
                    _currency_choices(old.receipt.allowed_price_currencies)
                    _currency_choices(seed.receipt.allowed_price_currencies)
                    if not set(seed.receipt.allowed_price_currencies) <= set(choices):
                        raise RemintDraftUnavailable("original replacement currencies outside choices")
            except Exception:
                raise RemintDraftUnavailable("original business terms unavailable") from None
            text = seed_text if bill_terms is None else _business_text(bill_terms)
            updates = ({"specification": {}, "receipt": {}} if business_fields is None
                       else _business_updates(business_fields))
            updates["specification"]["bill_terms"] = text
            if attribute_fields is not None:
                updates["specification"]["public_attributes"] = _attribute_updates(seed, attribute_fields)
            if allowed_currencies is not None:
                selected = _currency_choices(allowed_currencies)
                if choices is None or not set(selected) <= set(choices):
                    raise ValueError("selected currencies outside original choices")
                updates["receipt"]["allowed_price_currencies"] = selected
            try:
                result = edit_remint_draft(old, seed, updates)
            except (DomainError, ValueError):
                raise ValueError("unsigned business terms refused") from None
            result["attributeNames"] = attribute_names
            result["originalAttributes"] = old_attributes
            result["proposedAttributes"] = _attribute_values(result["specification"])
            result["requiredAttributeNames"] = seed.template.required_fields
            result["originalBusinessFields"] = old_fields
            result["proposedBusinessFields"] = _business_values(result["specification"])
            result["currencyChoices"] = choices
            result["originalCurrencies"] = old.receipt.allowed_price_currencies if choices is not None else None
        return old_text, result

    def render(self, csrf, locale="en", bill_terms=None, allowed_currencies=None, business_fields=None,
               attribute_fields=None):
        words = WORDS[locale]
        original, result = self.draft(bill_terms, allowed_currencies, business_fields, attribute_fields)
        proposed = result["specification"].bill_terms
        preview = ("" if bill_terms is None else '<section><h2>' + escape(words[4])
            + '</h2><pre>' + escape(proposed) + '</pre></section>')
        currency_form = ""
        if result["currencyChoices"] is not None:
            labels = CURRENCY_WORDS[locale]
            selected = result["specification"].receipt.allowed_price_currencies
            currency_form = ('<p>' + escape(labels[1]) + ': '
                + escape(", ".join(result["originalCurrencies"])) + '</p><fieldset><legend>'
                + escape(labels[0]) + '</legend><p>' + escape(labels[2]) + '</p>'
                + ''.join('<label><input type="checkbox" name="priceCurrency" value="'
                    + escape(code, quote=True) + '"' + (' checked' if code in selected else '')
                    + '>' + escape(code) + '</label>' for code in result["currencyChoices"])
                + '</fieldset>')
        business_form = '<fieldset><legend>' + escape(words[2]) + '</legend>'
        for key, label in zip(BUSINESS_FIELDS, BUSINESS_LABELS[locale]):
            value = result["proposedBusinessFields"][key]
            original_value = result["originalBusinessFields"][key]
            if key == "registrationComparison":
                control = ('<select name="' + key + '">'
                    + ''.join('<option value="' + option + '"'
                        + (' selected' if option == value else '') + '>' + option + '</option>'
                        for option in ("LT", "LTE")) + '</select>')
            else:
                control = ('<input name="' + key + '" value="' + escape(value, quote=True)
                    + '" maxlength="16384" required>')
            business_form += ('<label>' + escape(label) + control + '</label><p>'
                + escape(words[1]) + ': ' + escape(original_value) + '</p>')
        business_form += '</fieldset>'
        attribute_labels = ATTRIBUTE_WORDS[locale]
        attribute_form = ('<section><h2>' + escape(attribute_labels[1]) + '</h2><dl>'
            + ''.join('<dt>' + escape(name) + '</dt><dd>' + escape(value) + '</dd>'
                      for name, value in result["originalAttributes"].items()) + '</dl></section>'
            + '<fieldset><legend>' + escape(attribute_labels[0]) + '</legend><p>'
            + escape(attribute_labels[2]) + '</p>')
        for i, name in enumerate(result["attributeNames"]):
            attribute_form += ('<label>' + escape(name) + '<input name="attribute.'
                + str(i) + '" value="' + escape(result["proposedAttributes"].get(name, ""), quote=True)
                + '" maxlength="16384"'
                + (' required' if name in result["requiredAttributeNames"] else '') + '></label>')
        attribute_form += '</fieldset>'
        # Only complete public business fields and currency codes are rendered. No raw model,
        # account, asset address, mapping, fact hash or local diagnostic is served.
        return ('<p>' + escape(words[5]) + '</p><section><h2>' + escape(words[1])
            + '</h2><pre>' + escape(original) + '</pre></section>'
            + '<form method="post" action="/remint-draft" autocomplete="off">'
            + '<input type="hidden" name="csrf" value="' + escape(csrf, quote=True) + '">'
            + '<input type="hidden" name="lang" value="' + locale + '">'
            + '<label>' + escape(words[2]) + '<textarea name="billTerms" rows="16" '
            + 'maxlength="16384" required>' + escape(proposed) + '</textarea></label>'
            + business_form + attribute_form + currency_form + '<button type="submit">' + escape(words[3]) + '</button></form>' + preview)


def mount_remint_draft(server, editor):
    """Wire a constructed original server before its host starts serving."""
    if (type(server) is not RemintReviewWorkbenchServer
            or type(editor) is not RemintDraftEditorBinding
            or server.binding.exchange is not editor.access
            or server.binding.receipt_id != editor.receipt_id):
        raise ValueError("same original server, receipt and serialized access required")
    server.draft_editor = editor
    server.RequestHandlerClass = RemintDraftWorkbenchHandler
    return server


class RemintDraftWorkbenchHandler(RemintReviewWorkbenchHandler):
    @staticmethod
    def native_navigation(locale):
        return (RemintReviewWorkbenchHandler.native_navigation(locale)
            + '<nav><a href="/remint-draft?lang=' + locale + '">'
            + escape(WORDS[locale][0]) + '</a></nav>')

    def _draft_page(self, locale, text=None, currencies=None, business_fields=None, attribute_fields=None):
        return self._page(WORDS[locale][0],
            self.server.draft_editor.render(self.server.csrf, locale, text, currencies, business_fields, attribute_fields), locale,
            language_path="/remint-draft")

    def _refuse(self, status, locale="en"):
        self.close_connection = True
        self.send_body(status, WORDS[locale][7], Connection="close")

    def do_GET(self):
        request = urlsplit(self.path)
        if request.path != "/remint-draft":
            return super().do_GET()
        if not self.host_ok():
            return self._refuse(421)
        locale = "en"
        try:
            if request.fragment or len(request.query) > 64:
                raise ValueError("bounded locale required")
            query = parse_qs(request.query, strict_parsing=True,
                             keep_blank_values=True, max_num_fields=1)
            if set(query) - {"lang"} or any(len(value) != 1 for value in query.values()):
                raise ValueError("one locale only")
            locale = query.get("lang", ["en"])[0]
            if locale not in WORDS:
                raise ValueError("supported locale required")
        except ValueError:
            return self._refuse(400)
        try:
            self.send_body(200, self._draft_page(locale))
        except RemintDraftUnavailable:
            self.send_body(503, self._page(WORDS[locale][0],
                '<p role="alert">' + escape(WORDS[locale][6]) + '</p>', locale,
                language_path="/remint-draft"))

    def do_POST(self):
        request = urlsplit(self.path)
        if request.path != "/remint-draft":
            return super().do_POST()
        if not self.host_ok() or self.headers.get("Origin") != self.server.origin:
            return self._refuse(403)
        locale = "en"
        try:
            if (request.query or request.fragment or self.headers.get("Transfer-Encoding") is not None
                    or self.headers.get("Content-Type") != "application/x-www-form-urlencoded"):
                raise ValueError("plain bounded form required")
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= MAX_BODY:
                raise ValueError("bounded body required")
            raw = self.rfile.read(length)
            if len(raw) != length:
                raise ValueError("incomplete body")
            fields = parse_qs(raw.decode("utf-8"), strict_parsing=True,
                keep_blank_values=True, max_num_fields=110, errors="strict")
            enabled = self.server.draft_editor.read_currency_choices is not None
            required = {"csrf", "lang", "billTerms"}
            base_fields = required | ({"priceCurrency"} if enabled else set())
            has_business_fields = bool(set(fields) & set(BUSINESS_FIELDS))
            attribute_keys = {key for key in fields if key.startswith("attribute.")}
            if (len(attribute_keys) > 64
                    or any(re.fullmatch(r"attribute\.(0|[1-9][0-9]?)", key) is None
                           or len(fields[key]) != 1 for key in attribute_keys)):
                raise ValueError("bounded original attribute input fields required")
            exact_fields = (base_fields | attribute_keys
                            | (set(BUSINESS_FIELDS) if has_business_fields else set()))
            attribute_fields = ({key: fields[key][0] for key in attribute_keys}
                                if attribute_keys else None)
            if (set(fields) != exact_fields
                    or any(len(fields.get(key, ())) != 1
                           for key in required | (set(BUSINESS_FIELDS) if has_business_fields else set()))):
                raise ValueError("exact draft fields required")
            business_fields = ({key: fields[key][0] for key in BUSINESS_FIELDS}
                               if has_business_fields else None)
            currencies = tuple(fields["priceCurrency"]) if enabled else None
            if currencies is not None:
                _currency_choices(currencies)
            locale = fields["lang"][0]
            if locale not in WORDS:
                locale = "en"
                raise ValueError("supported locale required")
            token = fields["csrf"][0]
            if not token.isascii() or not secrets.compare_digest(token, self.server.csrf):
                return self._refuse(403, locale)
            text = _business_text(fields["billTerms"][0])
            self.send_body(200, self._draft_page(locale, text, currencies, business_fields, attribute_fields))
        except RemintDraftUnavailable:
            self.close_connection = True
            self.send_body(503, WORDS[locale][6], Connection="close")
        except TimeoutError:
            return self._refuse(408, locale)
        except (ValueError, UnicodeError):
            return self._refuse(400, locale)
