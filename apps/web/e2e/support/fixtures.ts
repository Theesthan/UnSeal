// Fictional e2e content in each language. No real person, office address or case.
export type Lang = "en" | "hi" | "ta";

export const CASE_ID = "3f0c9a8e-2b1d-4c5e-9f7a-1a2b3c4d5e6f";
export const QUESTION_IDS = [
  "9b2e4c1a-7d3f-4e8a-b6c5-0d1e2f3a4b5c",
  "1c3d5e7f-9a0b-4c1d-8e2f-3a4b5c6d7e8f",
  "7e6d5c4b-3a2f-4e1d-9c0b-8a7f6e5d4c3b",
];
export const AUTHORITY_ID = "5a4b3c2d-1e0f-4a9b-8c7d-6e5f4a3b2c1d";

interface QuestionText {
  original: string;
  rewritten: string;
  records: string[];
  reason: string;
}

export interface LangFixture {
  concern: string;
  followUps: string[];
  answer: string;
  authority: { name: string; name_ta: string; name_hi: string; designation: string; address: string };
  question: QuestionText;
  second: QuestionText;
  personal: { original: string; reason: string; suggestion: string };
  applicant: { name: string; address: string };
  place: string;
}

const authority = {
  name: "Controller of Examinations, Sample State University",
  name_ta: "தேர்வுக் கட்டுப்பாட்டு அலுவலர், மாதிரி மாநிலப் பல்கலைக்கழகம்",
  name_hi: "परीक्षा नियंत्रक, नमूना राज्य विश्वविद्यालय",
  designation: "Public Information Officer (Examinations)",
  address: "Office of the Controller of Examinations,\nSample State University,\n12 College Road, Sample Town",
};

export const FIXTURES: Record<Lang, LangFixture> = {
  ta: {
    concern:
      "என் செமஸ்டர் முடிவு தவறாகத் தெரிகிறது. கணிதம் II தாளில் மிகக் குறைந்த மதிப்பெண் வந்துள்ளது. என் விடைத்தாளைப் பார்க்க வேண்டும்.",
    followUps: [
      "எந்தப் பல்கலைக்கழகம் இந்தத் தேர்வை நடத்தியது?",
      "எந்தத் தேர்வு அமர்வு, எந்தப் பாடம்?",
      "நகலை அஞ்சலில் பெற விரும்புகிறீர்களா, நேரில் பெற விரும்புகிறீர்களா?",
    ],
    answer: "மாதிரி மாநிலப் பல்கலைக்கழகம், ஏப்ரல் 2026 அமர்வு, கணிதம் II. அஞ்சலில் வேண்டும்.",
    authority,
    question: {
      original: "என் மதிப்பெண் ஏன் இவ்வளவு குறைவாக உள்ளது?",
      rewritten:
        "ஏப்ரல் 2026 அமர்வில் நடந்த கணிதம் II தேர்வில், என் பதிவு எண்ணுக்கான மதிப்பீடு செய்யப்பட்ட விடைத்தாளின் சான்றளிக்கப்பட்ட நகலை வழங்கவும்.",
      records: ["மதிப்பீடு செய்யப்பட்ட விடைத்தாளின் சான்றளிக்கப்பட்ட நகல்"],
      reason:
        "'ஏன்' என்ற கேள்விக்கு அலுவலர் கருத்துச் சொல்ல வேண்டியதில்லை; ஆனால் அவரிடம் உள்ள விடைத்தாளின் நகலைத் தர வேண்டும்.",
    },
    second: {
      original: "மதிப்பீட்டாளர் சரியாகத் திருத்தினாரா?",
      rewritten:
        "மேற்கண்ட தாளுக்கான மதிப்பெண் பட்டியலின் சான்றளிக்கப்பட்ட நகலையும், கேள்வி வாரியான மதிப்பெண் விவரத்தையும் வழங்கவும்.",
      records: ["மதிப்பெண் பட்டியல்", "கேள்வி வாரியான மதிப்பெண் விவரம்"],
      reason: "கருத்துக் கேள்வியை, அலுவலகத்தில் உள்ள மதிப்பெண் பதிவுகளுக்கான கோரிக்கையாக மாற்றியுள்ளோம்.",
    },
    personal: {
      original: "என் வகுப்புத் தோழியின் மதிப்பெண் எவ்வளவு?",
      reason: "மற்றொரு மாணவியின் மதிப்பெண் அவருடைய தனிப்பட்ட தகவல்.",
      suggestion:
        "ஏப்ரல் 2026 அமர்வில் கணிதம் II தாளுக்கு மறுமதிப்பீடு கோரி விண்ணப்பித்த மாணவர்களின் மொத்த எண்ணிக்கையை வழங்கவும்.",
    },
    applicant: { name: "கவியா ஆர்.", address: "மாதிரி முகவரி 7, மாதிரி நகர்" },
    place: "மாதிரி நகர்",
  },
  hi: {
    concern:
      "मेरा सेमेस्टर का परिणाम गलत लगता है। गणित II में बहुत कम अंक आए हैं। मुझे अपनी उत्तर पुस्तिका देखनी है।",
    followUps: [
      "परीक्षा किस विश्वविद्यालय ने ली थी?",
      "कौन-सा सत्र और कौन-सा विषय?",
      "प्रति डाक से भेजी जाए या कार्यालय से ली जाए?",
    ],
    answer: "नमूना राज्य विश्वविद्यालय, अप्रैल 2026 सत्र, गणित II। डाक से।",
    authority,
    question: {
      original: "मेरे अंक इतने कम क्यों आए?",
      rewritten:
        "अप्रैल 2026 सत्र की गणित II परीक्षा में मेरे अनुक्रमांक की जाँची गई उत्तर पुस्तिका की प्रमाणित प्रति दें।",
      records: ["जाँची गई उत्तर पुस्तिका की प्रमाणित प्रति"],
      reason: "'क्यों' के बजाय यह कार्यालय के पास मौजूद रिकॉर्ड माँगता है।",
    },
    second: {
      original: "क्या परीक्षक ने ठीक से जाँचा?",
      rewritten: "ऊपर बताए गए पेपर की अंक सूची और प्रश्नवार अंकों के विवरण की प्रमाणित प्रति दें।",
      records: ["अंक सूची", "प्रश्नवार अंकों का विवरण"],
      reason: "राय पूछने के बजाय यह अंकों के रिकॉर्ड माँगता है।",
    },
    personal: {
      original: "मेरी सहपाठी को कितने अंक मिले?",
      reason: "दूसरी छात्रा के अंक उसकी निजी जानकारी हैं।",
      suggestion:
        "अप्रैल 2026 सत्र में गणित II के पुनर्मूल्यांकन के लिए आवेदन करने वाले छात्रों की कुल संख्या बताएँ।",
    },
    applicant: { name: "रीना शर्मा", address: "नमूना पता 7, नमूना नगर" },
    place: "नमूना नगर",
  },
  en: {
    concern:
      "My semester result looks wrong. I got very low marks in Mathematics II and I want to see my answer sheet.",
    followUps: [
      "Which university held the exam?",
      "Which exam session and which subject?",
      "Do you want the copy by post or in person?",
    ],
    answer: "Sample State University, April 2026 session, Mathematics II. By post.",
    authority,
    question: {
      original: "Why are my marks so low?",
      rewritten:
        "Provide a certified copy of my evaluated answer script for Mathematics II, April 2026 session.",
      records: ["Certified copy of the evaluated answer script"],
      reason: "Asks for a record the office holds instead of a reason.",
    },
    second: {
      original: "Did the examiner mark it properly?",
      rewritten:
        "Provide a certified copy of the mark list and the question-wise marks for the paper above.",
      records: ["Mark list", "Question-wise marks"],
      reason: "Turns an opinion question into a request for the marking records.",
    },
    personal: {
      original: "How many marks did my classmate get?",
      reason: "Another student's marks are that student's personal information.",
      suggestion:
        "Provide the total number of students who applied for revaluation of Mathematics II in the April 2026 session.",
    },
    applicant: { name: "Asha Verma", address: "7 Sample Street, Sample Town" },
    place: "Sample Town",
  },
};
