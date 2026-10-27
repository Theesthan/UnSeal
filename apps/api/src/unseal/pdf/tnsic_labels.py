"""The second appeal on the Tamil Nadu Information Commission form, in English, Tamil and Hindi.

Sources (opened 2026-10-27), linked from tnsic.gov.in/second.php:
- English: https://tnsic.gov.in/pdf/guidelines/appeal_format/sa_eng.pdf
- Tamil: https://tnsic.gov.in/pdf/guidelines/appeal_format/sa_tam.pdf
The English strings follow the English form (capitals normalised, "sec" spelt "section"). The
Tamil strings are the Tamil form's own wording as its text layer reads, except where a comment
says "reconstructed": those lines (the header, the four part headings, "Verification", the first
verification paragraph and the word for date) use a legacy font whose text layer is garbled, so
they were rebuilt from the garbled text and the English form and need a native reader to compare
them with the printed form. The Hindi strings are translations (no Hindi form exists).

Section numbers are slots ({request}, {transfer}, {first_appeal}, {second_appeal}) filled from the
rules. The form's complaint question cites a section no rule carries, so it is worded without the
number. Mandatory marks (*) are the form's own.
"""

TNSIC_TEXT: dict[str, dict[str, str]] = {
    "en": {
        "before": "Before the Tamil Nadu Information Commission",
        "title": "Second appeal under Section {second_appeal} of the {act}, with necessary copies "
        "enclosed",
        "appellant": "Details of Appellant",
        "name": "Name*",
        "guardian": "Father/Husband/Guardian Name*",
        "mobile": "Mobile Number*",
        "email": "Email",
        "gender": "Gender",
        "dob": "Date of Birth & Age",
        "country": "Country",
        "state": "State",
        "district": "District",
        "address": "Address*",
        "pin": "Pin Code",
        "mandatory": "(* Mandatory)",
        "part1": "I. Details of petition under section {request} of the {act}",
        "p1_1": "Date of petition to the PIO under section {request}*",
        "p1_2": "Details of PIO*",
        "p1_3": "Copy of petition under section {request} to be enclosed*",
        "p1_4": "Reply received from the PIO to the petition under section {request}",
        "p1_5": "If yes, copy of the reply to be enclosed",
        "p1_6": "Whether the petition under section {request} has been transferred to any other "
        "PIO under section {transfer}",
        "p1_7": "If yes, copy of the letter to be enclosed",
        "p1_8": "Details of any other/new PIO to whom the petition was transferred*",
        "p1_9": "Reply received from the new PIO to whom the petition was transferred",
        "p1_10": "If yes, copy of the reply to be enclosed",
        "part2": "II. Details of first appeal under section {first_appeal} of the {act}",
        "p2_1": "Date of appeal to the First Appellate Authority under section {first_appeal}*",
        "p2_2": "Details of First Appellate Authority*",
        "p2_3": "Copy of appeal petition to be enclosed*",
        "p2_4": "Reasons for preferring appeal under section {first_appeal}",
        "p2_5": "Reply received from the First Appellate Authority",
        "p2_6": "If yes, copy of the reply to be enclosed",
        "reasons1_from": "",
        "r1_not_furnished": "Reply not furnished by the PIO",
        "r_not_satisfactory": "Reply not satisfactory",
        "r_partial": "Partial reply",
        "r_improper": "Improper reply",
        "part3": "III. Details of second appeal under section {second_appeal} of the {act}",
        "p3_1": "Reasons for preferring appeal under section {second_appeal}",
        "reasons3_from": "",
        "r3_not_furnished": "Reply not furnished by the PIO/First Appellate Authority",
        "p3_2": "Grounds of appeal if necessary (Grievance)",
        "p3_3": "Whether you have filed any complaint petition in the Commission on this petition "
        "under section {request}? If yes, specify the complaint petition number and date (CP No. "
        "& Date)",
        "hearing": "IV. Details of hearing mode",
        "p4_1": "Mode of inquiry",
        "virtual": "Virtual",
        "direct": "Direct",
        "verification": "Verification",
        "declaration1": "I, {name}, S/o or D/o or W/o {blank}, the appellant herein, do hereby "
        "declare that the details and particulars furnished above are true and correct to the best "
        "of my knowledge and belief and I have not suppressed any material fact.",
        "declaration2": "I have not preferred any appeal previously to the Commission on the same "
        "issues raised in this appeal.",
        "pio": "{officer}",
        "faa": "First Appellate Authority",
        "yes": "Yes",
        "no": "No",
        "enclosed": "Enclosed",
        "not_applicable": "Not applicable",
        "received_note": "(received on {date})",
        "enclosures_heading": "Copies enclosed",
    },
    "ta": {
        "before": "தமிழ்நாடு தகவல் ஆணையம் முன்பாக",  # reconstructed
        "title": "{act}-ன் பிரிவு {second_appeal}-ன் படி இரண்டாம் மேல்முறையீடு மனு (உரிய "
        "நகல்களுடன் தாக்கல் செய்கிறேன்.) அது குறித்த விவரங்கள் பின்வருமாறு:",
        "appellant": "மேல்முறையீட்டாளர் விவரங்கள்",
        "name": "பெயர்*",
        "guardian": "தந்தை/ கணவர்/ காப்பாளர் பெயர்*",
        "mobile": "அலைபேசி எண்*",
        "email": "மின்அஞ்சல்",
        "gender": "பாலினம்",
        "dob": "பிறந்த தேதி & வயது",
        "country": "நாடு",
        "state": "மாநிலம்",
        "district": "மாவட்டம்",
        "address": "முகவரி*",
        "pin": "அஞ்சல் குறியீடு எண்",
        "mandatory": "(*அவசியம் பூர்த்தி செய்யவும்)",
        "part1": "I. தகவல் பெறும் உரிமை சட்டம் {request}-ன் படி, மனுவின் விவரம்",  # reconstructed
        "p1_1": "பிரிவு {request}-ன் கீழ் பொதுத் தகவல் அலுவலருக்கு அளித்த மனு நாள்*",
        "p1_2": "பொதுத் தகவல் அலுவலரின் விவரம்*",
        "p1_3": "பிரிவு {request}-ன் கீழ் பொதுத் தகவல் அலுவலருக்கு அளித்த மனுவின் நகல் இணைக்கவும்*",
        "p1_4": "பிரிவு {request}-ன் கீழ் அளித்த மனுவிற்கு பொதுத் தகவல் அலுவலரால் பதில் வழங்கப்பட்டுள்ளது.",
        "p1_5": "ஆம் எனில், நகல் இணைக்கவும்",
        "p1_6": "பிரிவு {request}-ன் கீழ் அளித்த மனுவானது சட்டப்பிரிவு {transfer}-ன் கீழ் பிற "
        "பொதுத் தகவல் அலுவலருக்கு மாற்றப்பட்டுள்ளது",
        "p1_7": "ஆம் எனில், நகல் இணைக்கவும்",
        "p1_8": "பிற / புதிய பொதுத் தகவல் அலுவலரின் விவரம்*",
        "p1_9": "பிரிவு {transfer}-ன் கீழ் மாறுதல் செய்யப்பட்ட மனுவிற்கு புதிய பொதுத் தகவல் "
        "அலுவலரால் பதில் அளிக்கப்பட்டது",
        "p1_10": "ஆம் எனில், நகல் இணைக்கவும்",
        "part2": "II. தகவல் பெறும் உரிமை சட்டம் {first_appeal}-ன் படி, முதல் மேல்முறையீட்டு மனுவின் "
        "விவரம்",  # reconstructed
        "p2_1": "பிரிவு {first_appeal}-ன் கீழ் முதல் மேல் முறையீட்டு அலுவலருக்கு அளித்த மனு நாள்*",
        "p2_2": "முதல் மேல் முறையீட்டு அலுவலரின் விவரம்*",
        "p2_3": "பிரிவு {first_appeal}-ன் கீழ் செய்த மேல் முறையீட்டு மனுவின் நகல் இணைக்கவும்.*",
        "p2_4": "பிரிவு {first_appeal}-ன் கீழ் மேல் முறையீடு செய்வதற்கான காரணம்",
        "p2_5": "பிரிவு {first_appeal}-ன் கீழ் முதல் மேல் முறையீடு அளித்த மனுவிற்கு மேல் முறையீட்டு "
        "அலுவலரால் பதில் வழங்கப்பட்டது",
        "p2_6": "ஆம் எனில், நகல் இணைக்கவும்",
        "reasons1_from": "பொதுத் தகவல் அலுவலரிடமிருந்து",
        "r1_not_furnished": "தகவல் கிடைக்கப்பெறவில்லை",
        "r_not_satisfactory": "கிடைக்கப் பெற்ற தகவல் திருப்திகரமாக இல்லை",
        "r_partial": "கிடைக்கப் பெற்ற தகவல் முழுமையானதாக இல்லை",
        "r_improper": "கிடைக்கப்பெற்ற தகவல் சரியானதாக இல்லை",
        "part3": "III. தகவல் பெறும் உரிமை சட்டம் {second_appeal}-ன் படி, இரண்டாம் மேல்முறையீட்டு "
        "மனுவின் விவரம்",  # reconstructed
        "p3_1": "பிரிவு {second_appeal}-ன் கீழ் இரண்டாம் மேல் முறையீடு செய்வதற்கான காரணம்",
        "reasons3_from": "பொதுத் தகவல் அலுவலரிடமிருந்து / முதல் மேல் முறையீட்டு அலுவலரிடமிருந்து",
        "r3_not_furnished": "தகவல் கிடைக்கப்பெறவில்லை",
        "p3_2": "மனுதாரர் மேல் முறையீட்டிற்கான காரணம் தேவைப்படின்",
        # The form's "சட்டப்பிரிவு <section>-ன் கீழ்" before "புகார் மனு" is left out (no rule).
        "p3_3": "இந்த {request} மனுவின் மீது புகார் மனு ஏதும் இவ்வாணையத்தில் தாக்கல் "
        "செய்துள்ளீர்களா? ஆம் எனில், அப்புகார் மனுவின் எண் மற்றும் தேதி (CP No & Date) போன்ற "
        "விபரங்களை குறிப்பிடவும்",
        "hearing": "IV. விசாரணைக்கான விருப்பத்தை தேர்வு செய்யும் விவரம்",  # reconstructed
        "p4_1": "விசாரணை முறை",
        "virtual": "காணொளி காட்சி விசாரணை",
        "direct": "நேரடி விசாரணை",
        "verification": "உறுதிமொழி",  # reconstructed
        # Reconstructed (the form prints த/பெ / க/பெ, father's or husband's name, after the blank).
        "declaration1": "விண்ணப்பதாரராகிய நான், {name}, த/பெ / க/பெ {blank}, என்னால் "
        "சமர்ப்பிக்கப்பட்டுள்ள விவரங்கள் மற்றும் தகவல்கள் அனைத்தும் எனக்கு நேரடியாக தெரிந்தவை "
        "என்றும் அவை அனைத்தும் நான் அறிந்தவகையில் உண்மை எனவும், சரியானவை எனவும் இதன்மூலம் "
        "உறுதியளிக்கிறேன்.",
        "declaration2": "நான் இதற்கு முன்னர் இதே பொருள் குறித்து ஆணையத்திடம் எந்த மேல்முறையீடும் "
        "செய்யவில்லை என்றும் உறுதியளிக்கிறேன்.",
        "pio": "{officer}",
        "faa": "முதல் மேல் முறையீட்டு அலுவலர்",
        "yes": "ஆம்",
        "no": "இல்லை",
        "enclosed": "இணைப்பு நகல்",  # the form's own answer in part II, row 3
        # Native review needed: the three strings below are UnSeal's, not the form's.
        "not_applicable": "பொருந்தாது",
        "received_note": "({date} அன்று கிடைத்தது)",
        "enclosures_heading": "இணைக்கப்பட்ட நகல்கள்",
    },
    # Native review needed: every Hindi string in this block (translated from the English form).
    "hi": {
        "before": "तमिलनाडु सूचना आयोग के समक्ष",
        "title": "{act} की धारा {second_appeal} के अंतर्गत द्वितीय अपील, आवश्यक प्रतियों सहित",
        "appellant": "अपीलार्थी का विवरण",
        "name": "नाम*",
        "guardian": "पिता/पति/अभिभावक का नाम*",
        "mobile": "मोबाइल नंबर*",
        "email": "ईमेल",
        "gender": "लिंग",
        "dob": "जन्म तिथि और आयु",
        "country": "देश",
        "state": "राज्य",
        "district": "जिला",
        "address": "पता*",
        "pin": "पिन कोड",
        "mandatory": "(* अनिवार्य)",
        "part1": "I. {act} की धारा {request} के अंतर्गत आवेदन का विवरण",
        "p1_1": "धारा {request} के अंतर्गत {officer} को आवेदन की तिथि*",
        "p1_2": "{officer} का विवरण*",
        "p1_3": "धारा {request} के अंतर्गत आवेदन की प्रति संलग्न करें*",
        "p1_4": "धारा {request} के अंतर्गत आवेदन पर {officer} से उत्तर प्राप्त हुआ",
        "p1_5": "यदि हाँ, तो उत्तर की प्रति संलग्न करें",
        "p1_6": "क्या धारा {request} के अंतर्गत आवेदन धारा {transfer} के अंतर्गत किसी अन्य {officer} "
        "को अंतरित किया गया है",
        "p1_7": "यदि हाँ, तो पत्र की प्रति संलग्न करें",
        "p1_8": "उस अन्य/नए {officer} का विवरण जिसे आवेदन अंतरित किया गया*",
        "p1_9": "जिस नए {officer} को आवेदन अंतरित किया गया, उससे उत्तर प्राप्त हुआ",
        "p1_10": "यदि हाँ, तो उत्तर की प्रति संलग्न करें",
        "part2": "II. {act} की धारा {first_appeal} के अंतर्गत प्रथम अपील का विवरण",
        "p2_1": "धारा {first_appeal} के अंतर्गत प्रथम अपीलीय प्राधिकारी को अपील की तिथि*",
        "p2_2": "प्रथम अपीलीय प्राधिकारी का विवरण*",
        "p2_3": "अपील की प्रति संलग्न करें*",
        "p2_4": "धारा {first_appeal} के अंतर्गत अपील करने के कारण",
        "p2_5": "प्रथम अपीलीय प्राधिकारी से उत्तर प्राप्त हुआ",
        "p2_6": "यदि हाँ, तो उत्तर की प्रति संलग्न करें",
        "reasons1_from": "",
        "r1_not_furnished": "{officer} द्वारा उत्तर नहीं दिया गया",
        "r_not_satisfactory": "उत्तर संतोषजनक नहीं",
        "r_partial": "आंशिक उत्तर",
        "r_improper": "अनुचित उत्तर",
        "part3": "III. {act} की धारा {second_appeal} के अंतर्गत द्वितीय अपील का विवरण",
        "p3_1": "धारा {second_appeal} के अंतर्गत अपील करने के कारण",
        "reasons3_from": "",
        "r3_not_furnished": "{officer}/प्रथम अपीलीय प्राधिकारी द्वारा उत्तर नहीं दिया गया",
        "p3_2": "अपील के आधार, यदि आवश्यक हों (शिकायत)",
        "p3_3": "क्या आपने धारा {request} के इस आवेदन पर आयोग में कोई शिकायत याचिका दायर की है? यदि "
        "हाँ, तो शिकायत याचिका संख्या और तिथि (CP No. & Date) बताएँ",
        "hearing": "IV. सुनवाई के माध्यम का विवरण",
        "p4_1": "जाँच का माध्यम",
        "virtual": "वर्चुअल",
        "direct": "प्रत्यक्ष",
        "verification": "सत्यापन",
        "declaration1": "मैं, {name}, पुत्र/पुत्री/पत्नी {blank}, इसमें अपीलार्थी, एतद्द्वारा घोषणा "
        "करता/करती हूँ कि ऊपर दिए गए विवरण और विशिष्टियां मेरी पूर्ण जानकारी और विश्वास के अनुसार "
        "सत्य और सही हैं तथा मैंने कोई महत्वपूर्ण तथ्य नहीं छिपाया है।",
        "declaration2": "मैंने इस अपील में उठाए गए उन्हीं मुद्दों पर पहले आयोग में कोई अपील प्रस्तुत नहीं की है।",
        "pio": "{officer}",
        "faa": "प्रथम अपीलीय प्राधिकारी",
        "yes": "हाँ",
        "no": "नहीं",
        "enclosed": "संलग्न",
        "not_applicable": "लागू नहीं",
        "received_note": "({date} को प्राप्त)",
        "enclosures_heading": "संलग्न प्रतियाँ",
    },
}

TNSIC_ENCLOSURES: dict[str, dict[str, str]] = {
    "en": {
        "application": "Copy of the petition under section {request}",
        "pio_reply": "Copy of the reply from the PIO",
        "transfer_letter": "Copy of the transfer letter under section {transfer}",
        "first_appeal": "Copy of the appeal petition under section {first_appeal}",
        "faa_order": "Copy of the reply from the First Appellate Authority",
        "relied_documents": "Copies of other documents relied upon",
        "index": "Index of the documents enclosed",
    },
    # application and first_appeal are the form's rows I.3 and II.3 without "இணைக்கவும்".
    # Native review needed: the other five lines.
    "ta": {
        "application": "பிரிவு {request}-ன் கீழ் பொதுத் தகவல் அலுவலருக்கு அளித்த மனுவின் நகல்",
        "pio_reply": "பொதுத் தகவல் அலுவலரின் பதிலின் நகல்",
        "transfer_letter": "பிரிவு {transfer}-ன் கீழ் மனுவை மாற்றிய கடிதத்தின் நகல்",
        "first_appeal": "பிரிவு {first_appeal}-ன் கீழ் செய்த மேல் முறையீட்டு மனுவின் நகல்",
        "faa_order": "முதல் மேல் முறையீட்டு அலுவலரின் பதிலின் நகல்",
        "relied_documents": "சார்ந்துள்ள பிற ஆவணங்களின் நகல்கள்",
        "index": "இணைக்கப்பட்ட ஆவணங்களின் அட்டவணை",
    },
    # Native review needed: every Hindi line.
    "hi": {
        "application": "धारा {request} के अंतर्गत आवेदन की प्रति",
        "pio_reply": "{officer} के उत्तर की प्रति",
        "transfer_letter": "धारा {transfer} के अंतर्गत अंतरण पत्र की प्रति",
        "first_appeal": "धारा {first_appeal} के अंतर्गत अपील की प्रति",
        "faa_order": "प्रथम अपीलीय प्राधिकारी के उत्तर की प्रति",
        "relied_documents": "अन्य संदर्भित दस्तावेजों की प्रतियाँ",
        "index": "संलग्न दस्तावेजों की अनुक्रमणिका",
    },
}

# The form ends "Place", "Date", "*Signature of the Appellant". Tamil: இடம் and the signature
# line are the form's text; தேதி is reconstructed. Native review needed: the Hindi line.
TNSIC_SIGN: dict[str, dict[str, str]] = {
    "en": {"signer": "Appellant", "signature": "*Signature of the Appellant"},
    "ta": {
        "signer": "மேல்முறையீட்டாளர்",
        "signature": "*மேல்முறையீட்டாளரின் கையொப்பம்",
        "date": "தேதி",
        "place": "இடம்",
    },
    "hi": {"signer": "अपीलार्थी", "signature": "*अपीलार्थी के हस्ताक्षर"},
}
