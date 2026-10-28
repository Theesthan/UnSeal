"""The second appeal to the Central Information Commission: RTI Rules 2012, rule 8 and the
Appendix "Format of appeal" (11 items), in English, Hindi and Tamil.

Sources (opened 2026-10-27):
- English: https://cic.gov.in/sites/default/files/RTIRules2012_Eng.pdf (G.S.R. 603(E)).
- Hindi: https://cic.gov.in/sites/default/files/RTIRules2012_Hindi.pdf, the Hindi Gazette text of
  the same notification (परिशिष्ट, "अपील का रूपविधान").
The English and Hindi item headings and the copies to enclose are the published wording (English
capitals normalised). The rules use "प्रथम अपील प्राधिकारी" for the First Appellate Authority, so
the Hindi strings here do too. No official Tamil text of these rules was found, so every Tamil
string is a translation.

Slots: {act}, {officer}, {public_authority} are filled from the glossary; section slots
({request}, {transfer}, {first_appeal}, {second_appeal}) by the renderer from the rules; {name},
{date}, {filed_on} and the like by the renderer from the case.
"""

CIC_TEXT: dict[str, dict[str, str]] = {
    "en": {
        "title": "Second appeal under Section {second_appeal} of the {act}",
        "before": "Before the Central Information Commission",
        "item1": "Name and address of the appellant",
        "item2": "Name and address of the Central Public Information Officer to whom the "
        "application was addressed",
        "item3": "Name and address of the Central Public Information Officer who gave reply to "
        "the application",
        "item4": "Name and address of the First Appellate Authority who decided the first appeal",
        "item5": "Particulars of the application",
        "item6": "Particulars of the order(s) including number, if any, against which the appeal "
        "is preferred",
        "item7": "Brief facts leading to the appeal",
        "item8": "Prayer or relief sought",
        "item9": "Grounds for the prayer or relief",
        "item10": "Any other information relevant to the appeal",
        "item11": "Verification/authentication by the appellant",
        "cpio": "Central {officer}",
        "faa": "First Appellate Authority",
        "phone": "Phone",
        "no_reply_item": "No reply was received.",
        "transferred": "Transferred under Section {transfer} to",
        "order_reply": "Reply of the Central {officer}",
        "received_on_date": "Received on {date}",
        "no_reply": "No reply was received",
        "order_appeal": "First appeal filed on",
        "order_faa": "Order of the First Appellate Authority",
        "no_order": "No order was passed by the First Appellate Authority",
        "order_number": "Number of the order, if any",
        "facts_filed": "The application under Section {request} was filed on {filed_on} and "
        "received by the {public_authority} on {received_on}.",
        "facts_transfer": "It was transferred under Section {transfer} of the Act to "
        "{transferred_to}.",
        "facts_reply": "The reply was due by {due_on} and was received on {reply_on}.",
        "facts_no_reply": "The reply was due by {due_on}, but no reply was received.",
        "facts_appeal": "The first appeal under Section {first_appeal} was filed on {appeal_on}.",
        "facts_order": "The order of the First Appellate Authority was received on {order_on}.",
        "facts_no_order": "The First Appellate Authority passed no order on the first appeal.",
        "prayer": "I request the Commission to direct the Central {officer} to provide the "
        "information sought in my application.",
        "none": "None.",
        "declaration": "I, {name}, the appellant, declare that the particulars given in this "
        "appeal are true and correct to the best of my knowledge and belief, and that the "
        "documents enclosed are true copies.",
        "enclosures_heading": "Documents enclosed",
    },
    # The item headings (item1 to item11) are the Gazette's Hindi text. Native review needed:
    # every other Hindi string in this block.
    "hi": {
        "title": "{act} की धारा {second_appeal} के अंतर्गत द्वितीय अपील",
        "before": "केंद्रीय सूचना आयोग के समक्ष",
        "item1": "अपीलार्थी का नाम और पता",
        "item2": "केंद्रीय लोक सूचना अधिकारी का नाम और पता, जिसे आवेदन संबोधित किया गया था",
        "item3": "केंद्रीय लोक सूचना अधिकारी का नाम और पता, जिसने आवेदन का उत्तर दिया था",
        "item4": "प्रथम अपील प्राधिकारी का नाम और पता, जिसने प्रथम अपील का विनिश्चय किया था",
        "item5": "आवेदन की विशिष्टियां",
        "item6": "ऐसे आदेश (आदेशों) की, संख्यांक सहित, यदि कोई हो, जिसके (जिनके) विरुद्ध अपील की गई "
        "है, विशिष्टियां",
        "item7": "अपील के संक्षिप्त तथ्य, जिनके कारण अपील की गई है",
        "item8": "प्रार्थना या ईप्सित अनुतोष",
        "item9": "प्रार्थना या अनुतोष के आधार",
        "item10": "अपील से सुसंगत कोई अन्य सूचना",
        "item11": "अपीलार्थी द्वारा सत्यापन/अधिप्रमाणन",
        "cpio": "केंद्रीय {officer}",
        "faa": "प्रथम अपील प्राधिकारी",
        "phone": "फोन",
        "no_reply_item": "कोई उत्तर प्राप्त नहीं हुआ।",
        "transferred": "धारा {transfer} के अंतर्गत अंतरित कार्यालय",
        "order_reply": "केंद्रीय {officer} का उत्तर",
        "received_on_date": "{date} को प्राप्त",
        "no_reply": "कोई उत्तर प्राप्त नहीं हुआ",
        "order_appeal": "प्रथम अपील प्रस्तुत करने की तिथि",
        "order_faa": "प्रथम अपील प्राधिकारी का आदेश",
        "no_order": "प्रथम अपील प्राधिकारी द्वारा कोई आदेश पारित नहीं किया गया",
        "order_number": "आदेश का संख्यांक, यदि कोई हो",
        "facts_filed": "धारा {request} के अंतर्गत आवेदन {filed_on} को प्रस्तुत किया गया और {received_on} "
        "को {public_authority} को प्राप्त हुआ।",
        "facts_transfer": "इसे अधिनियम की धारा {transfer} के अंतर्गत {transferred_to} को अंतरित किया "
        "गया।",
        "facts_reply": "उत्तर देने की अंतिम तिथि {due_on} थी, और उत्तर {reply_on} को प्राप्त हुआ।",
        "facts_no_reply": "उत्तर देने की अंतिम तिथि {due_on} थी, परंतु कोई उत्तर प्राप्त नहीं हुआ।",
        "facts_appeal": "धारा {first_appeal} के अंतर्गत प्रथम अपील {appeal_on} को प्रस्तुत की गई।",
        "facts_order": "प्रथम अपील प्राधिकारी का आदेश {order_on} को प्राप्त हुआ।",
        "facts_no_order": "प्रथम अपील प्राधिकारी ने प्रथम अपील पर कोई आदेश पारित नहीं किया।",
        "prayer": "अनुरोध है कि आयोग केंद्रीय {officer} को मेरे आवेदन में माँगी गई सूचना उपलब्ध "
        "कराने का निर्देश दे।",
        "none": "कुछ नहीं।",
        "declaration": "मैं, {name}, अपीलार्थी, घोषणा करता/करती हूँ कि इस अपील में दी गई विशिष्टियां "
        "मेरी पूर्ण जानकारी और विश्वास के अनुसार सत्य और सही हैं, तथा संलग्न दस्तावेज सही प्रतियां हैं।",
        "enclosures_heading": "संलग्न दस्तावेज",
    },
    # Native review needed: every Tamil string in this block (no official Tamil text found).
    "ta": {
        "title": "{act} பிரிவு {second_appeal}-இன் கீழ் இரண்டாம் மேல்முறையீடு",
        "before": "மத்திய தகவல் ஆணையம் முன்பாக",
        "item1": "மேல்முறையீட்டாளரின் பெயர் மற்றும் முகவரி",
        "item2": "விண்ணப்பம் அனுப்பப்பட்ட மத்திய பொதுத் தகவல் அலுவலரின் பெயர் மற்றும் முகவரி",
        "item3": "விண்ணப்பத்திற்குப் பதில் அளித்த மத்திய பொதுத் தகவல் அலுவலரின் பெயர் மற்றும் முகவரி",
        "item4": "முதல் மேல்முறையீட்டை முடிவு செய்த முதல் மேல்முறையீட்டு அலுவலரின் பெயர் மற்றும் முகவரி",
        "item5": "விண்ணப்பத்தின் விவரங்கள்",
        "item6": "மேல்முறையீடு செய்யப்படும் ஆணை(கள்) பற்றிய விவரங்கள், எண் ஏதேனும் இருப்பின் அதனுடன்",
        "item7": "மேல்முறையீட்டுக்கு வழிவகுத்த சுருக்கமான உண்மைகள்",
        "item8": "கோரும் வேண்டுகோள் அல்லது நிவாரணம்",
        "item9": "வேண்டுகோள் அல்லது நிவாரணத்திற்கான காரணங்கள்",
        "item10": "மேல்முறையீடு தொடர்பான பிற தகவல்கள்",
        "item11": "மேல்முறையீட்டாளரின் சரிபார்ப்பு / உறுதிப்படுத்தல்",
        "cpio": "மத்திய {officer}",
        "faa": "முதல் மேல்முறையீட்டு அலுவலர்",
        "phone": "தொலைபேசி",
        "no_reply_item": "பதில் எதுவும் கிடைக்கவில்லை.",
        "transferred": "பிரிவு {transfer}-இன் கீழ் மாற்றப்பட்ட அலுவலகம்",
        "order_reply": "மத்திய பொதுத் தகவல் அலுவலரின் பதில்",
        "received_on_date": "{date} அன்று கிடைத்தது",
        "no_reply": "பதில் எதுவும் கிடைக்கவில்லை",
        "order_appeal": "முதல் மேல்முறையீடு தாக்கல் செய்த நாள்",
        "order_faa": "முதல் மேல்முறையீட்டு அலுவலரின் ஆணை",
        "no_order": "முதல் மேல்முறையீட்டு அலுவலர் எந்த ஆணையும் பிறப்பிக்கவில்லை",
        "order_number": "ஆணையின் எண் (ஏதேனும் இருப்பின்)",
        "facts_filed": "பிரிவு {request}-இன் கீழ் விண்ணப்பம் {filed_on} அன்று தாக்கல் செய்யப்பட்டது; "
        "{public_authority} அதை {received_on} அன்று பெற்றது.",
        "facts_transfer": "அது சட்டத்தின் பிரிவு {transfer}-இன் கீழ் பின்வரும் அலுவலகத்திற்கு "
        "மாற்றப்பட்டது: {transferred_to}.",
        "facts_reply": "பதில் அளிக்க வேண்டிய கடைசி நாள் {due_on}; பதில் {reply_on} அன்று கிடைத்தது.",
        "facts_no_reply": "பதில் அளிக்க வேண்டிய கடைசி நாள் {due_on}; ஆனால் பதில் எதுவும் கிடைக்கவில்லை.",
        "facts_appeal": "பிரிவு {first_appeal}-இன் கீழ் முதல் மேல்முறையீடு {appeal_on} அன்று தாக்கல் "
        "செய்யப்பட்டது.",
        "facts_order": "முதல் மேல்முறையீட்டு அலுவலரின் ஆணை {order_on} அன்று கிடைத்தது.",
        "facts_no_order": "முதல் மேல்முறையீட்டு அலுவலர் முதல் மேல்முறையீட்டின் மீது எந்த ஆணையும் பிறப்பிக்கவில்லை.",
        "prayer": "எனது விண்ணப்பத்தில் கோரப்பட்ட தகவல்களை மத்திய {officer} வழங்குமாறு ஆணையம் "
        "உத்தரவிட வேண்டுமெனக் கேட்டுக்கொள்கிறேன்.",
        "none": "இல்லை.",
        "declaration": "மேல்முறையீட்டாளராகிய நான், {name}, இந்த மேல்முறையீட்டில் அளித்துள்ள "
        "விவரங்கள் எனக்குத் தெரிந்தவரையிலும் நம்பிக்கையின்படியும் உண்மையானவை, சரியானவை என்றும், "
        "இணைக்கப்பட்ட ஆவணங்கள் உண்மையான நகல்கள் என்றும் உறுதியளிக்கிறேன்.",
        "enclosures_heading": "இணைக்கப்பட்ட ஆவணங்கள்",
    },
}

# Rule 8 (i) to (vi); "if any" is dropped because a copy the case cannot have is left out. The
# transfer letter is not in rule 8 but every format gets a line for every code.
CIC_ENCLOSURES: dict[str, dict[str, str]] = {
    "en": {
        "application": "A copy of the application submitted to the Central {officer}",
        "pio_reply": "A copy of the reply received from the Central {officer}",
        "transfer_letter": "A copy of the letter transferring the application under Section "
        "{transfer}",
        "first_appeal": "A copy of the appeal made to the First Appellate Authority",
        "faa_order": "A copy of the order received from the First Appellate Authority",
        "relied_documents": "Copies of other documents relied upon and referred to in this appeal",
        "index": "An index of the documents referred to in this appeal",
    },
    # Gazette Hindi of rule 8 (i) to (vi). Native review needed: transfer_letter only.
    "hi": {
        "application": "केंद्रीय लोक सूचना अधिकारी को प्रस्तुत किए गए आवेदन की एक प्रति",
        "pio_reply": "केंद्रीय लोक सूचना अधिकारी से प्राप्त उत्तर की एक प्रति",
        "transfer_letter": "धारा {transfer} के अंतर्गत आवेदन के अंतरण पत्र की एक प्रति",
        "first_appeal": "प्रथम अपील प्राधिकारी को की गई अपील की एक प्रति",
        "faa_order": "प्रथम अपील प्राधिकारी से प्राप्त आदेश की एक प्रति",
        "relied_documents": "ऐसे अन्य दस्तावेजों की प्रतियां जिनका अपीलार्थी द्वारा अवलंब लिया गया है "
        "और जिन्हें उसने अपील में निर्दिष्ट किया है",
        "index": "अपील में निर्दिष्ट दस्तावेजों की एक अनुक्रमणिका",
    },
    # Native review needed: every Tamil line. Inflected forms of the officer title are written out
    # (அலுவலருக்கு, அலுவலரிடமிருந்து): a case ending glued to the {officer} slot would be malformed.
    "ta": {
        "application": "மத்திய பொதுத் தகவல் அலுவலருக்கு அளித்த விண்ணப்பத்தின் நகல்",
        "pio_reply": "மத்திய பொதுத் தகவல் அலுவலரிடமிருந்து பெற்ற பதிலின் நகல்",
        "transfer_letter": "பிரிவு {transfer}-இன் கீழ் விண்ணப்பத்தை மாற்றிய கடிதத்தின் நகல்",
        "first_appeal": "முதல் மேல்முறையீட்டு அலுவலருக்கு அளித்த மேல்முறையீட்டின் நகல்",
        "faa_order": "முதல் மேல்முறையீட்டு அலுவலரிடமிருந்து பெற்ற ஆணையின் நகல்",
        "relied_documents": "இந்த மேல்முறையீட்டில் குறிப்பிட்டு, சார்ந்துள்ள பிற ஆவணங்களின் நகல்கள்",
        "index": "இந்த மேல்முறையீட்டில் குறிப்பிட்ட ஆவணங்களின் அட்டவணை",
    },
}

# The signature block: the application's own labels, with the appellant as signer.
CIC_SIGN: dict[str, dict[str, str]] = {
    "en": {"signer": "Appellant"},
    "hi": {"signer": "अपीलार्थी"},
    "ta": {"signer": "மேல்முறையீட்டாளர்"},
}
