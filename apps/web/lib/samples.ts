// FR-13 sample gallery: three fictional cases with canned content. No API calls, no personal
// data: every applicant, office and address is made up, and every date is a sample date.
// No fee, payment mode or section number appears here; the sample checklist says those come
// from the official rules in a real case.
import type { Case, Language, Question, ValidationFlag } from "./types";

export const SAMPLE_SLUGS = ["answer-sheet", "ward-road", "passport-delay"] as const;
export type SampleSlug = (typeof SAMPLE_SLUGS)[number];

export interface Sample {
  slug: SampleSlug;
  language: Language;
  concern: string;
  followUps: { question: string; answer: string }[];
  authority: { name: string; designation: string; address: string };
  applicant: { name: string; place: string };
  questions: Question[];
  flags: ValidationFlag[];
  timeline: Pick<Case, "status" | "filed_on" | "received_on" | "received_estimated" | "deadlines">;
}

function q(
  position: number,
  fields: Omit<Question, "id" | "position" | "personal_information" | "suggestion"> &
    Partial<Pick<Question, "personal_information" | "suggestion">>,
): Question {
  return {
    id: `sample-${position}`,
    position,
    personal_information: false,
    suggestion: null,
    ...fields,
  };
}

const answerSheet: Sample = {
  slug: "answer-sheet",
  language: "ta",
  concern:
    "என் செமஸ்டர் முடிவு தவறாகத் தெரிகிறது. கணிதம் II தாளில் எனக்கு மிகக் குறைந்த மதிப்பெண் வந்துள்ளது. என் விடைத்தாளைப் பார்க்க வேண்டும்.",
  followUps: [
    {
      question: "எந்தப் பல்கலைக்கழகம் இந்தத் தேர்வை நடத்தியது?",
      answer: "மாதிரி மாநிலப் பல்கலைக்கழகம்.",
    },
    { question: "எந்தத் தேர்வு அமர்வு, எந்தப் பாடம்?", answer: "ஏப்ரல் 2026 அமர்வு, கணிதம் II." },
    {
      question: "நகலை எப்படிப் பெற விரும்புகிறீர்கள்: அஞ்சலிலா, நேரிலா?",
      answer: "அஞ்சலில்.",
    },
  ],
  authority: {
    name: "தேர்வுக் கட்டுப்பாட்டு அலுவலர், மாதிரி மாநிலப் பல்கலைக்கழகம்",
    designation: "பொதுத் தகவல் அலுவலர், தேர்வுப் பிரிவு",
    address: "தேர்வுக் கட்டுப்பாட்டு அலுவலகம்,\nமாதிரி மாநிலப் பல்கலைக்கழகம்,\n12, கல்லூரிச் சாலை, மாதிரி நகர்",
  },
  applicant: { name: "கவியா ஆர். (கற்பனைப் பெயர்)", place: "மாதிரி நகர்" },
  questions: [
    q(1, {
      original_text: "என் மதிப்பெண் ஏன் இவ்வளவு குறைவாக உள்ளது?",
      rewritten_text:
        "ஏப்ரல் 2026 அமர்வில் நடந்த கணிதம் II தேர்வில், என் பதிவு எண்ணுக்கான மதிப்பீடு செய்யப்பட்ட விடைத்தாளின் சான்றளிக்கப்பட்ட நகலை வழங்கவும்.",
      records_requested: ["மதிப்பீடு செய்யப்பட்ட விடைத்தாளின் சான்றளிக்கப்பட்ட நகல்"],
      reason:
        "'ஏன்' என்ற கேள்விக்கு அலுவலர் கருத்துச் சொல்ல வேண்டியதில்லை; ஆனால் அவரிடம் உள்ள விடைத்தாளின் நகலைத் தர வேண்டும்.",
      accepted: true,
    }),
    q(2, {
      original_text: "மதிப்பீட்டாளர் சரியாகத் திருத்தினாரா?",
      rewritten_text:
        "மேற்கண்ட தாளுக்கான மதிப்பெண் பட்டியலின் சான்றளிக்கப்பட்ட நகலையும், கேள்வி வாரியான மதிப்பெண் விவரத்தையும் வழங்கவும்.",
      records_requested: ["மதிப்பெண் பட்டியல்", "கேள்வி வாரியான மதிப்பெண் விவரம்"],
      reason: "கருத்துக் கேள்வியை, அலுவலகத்தில் உள்ள மதிப்பெண் பதிவுகளுக்கான கோரிக்கையாக மாற்றியுள்ளோம்.",
      accepted: false,
    }),
    q(3, {
      original_text: "என் வகுப்புத் தோழியின் மதிப்பெண் எவ்வளவு?",
      rewritten_text: "",
      records_requested: [],
      reason: "மற்றொரு மாணவியின் மதிப்பெண் அவருடைய தனிப்பட்ட தகவல்.",
      personal_information: true,
      suggestion:
        "ஏப்ரல் 2026 அமர்வில் கணிதம் II தாளுக்கு மறுமதிப்பீடு கோரி விண்ணப்பித்த மாணவர்களின் மொத்த எண்ணிக்கையை வழங்கவும்.",
      accepted: false,
    }),
  ],
  flags: [
    { code: "personal_information", severity: "warn", question: 2, basis: null, under_challenge: true },
  ],
  timeline: {
    status: "reply_due",
    filed_on: "2026-11-02",
    received_on: "2026-11-09",
    received_estimated: true,
    deadlines: [
      { kind: "pio_reply", due_on: "2026-12-09", due_at: null, estimated: true },
      { kind: "first_appeal", due_on: "2027-01-08", due_at: null, estimated: true },
    ],
  },
};

const wardRoad: Sample = {
  slug: "ward-road",
  language: "hi",
  concern:
    "हमारे वार्ड की सड़क छह महीने पहले बनी थी और अब फिर से टूट गई है। मुझे जानना है कि इस पर कितना पैसा खर्च हुआ और काम किसने किया।",
  followUps: [
    {
      question: "सड़क किस वार्ड और किस इलाके में है?",
      answer: "वार्ड 12, स्टेशन रोड से बाज़ार चौक तक।",
    },
    { question: "काम लगभग कब हुआ था?", answer: "अप्रैल 2026 में।" },
    {
      question: "आप रिकॉर्ड की प्रतियाँ डाक से चाहते हैं या स्वयं लेने आएँगे?",
      answer: "डाक से।",
    },
  ],
  authority: {
    name: "कार्यपालक अभियंता, वार्ड 12, नमूना नगर निगम",
    designation: "लोक सूचना अधिकारी, अभियांत्रिकी विभाग",
    address: "अभियांत्रिकी विभाग,\nनमूना नगर निगम, सिविक सेंटर,\nनमूना नगर",
  },
  applicant: { name: "रमेश कुमार (काल्पनिक नाम)", place: "नमूना नगर" },
  questions: [
    q(1, {
      original_text: "सड़क इतनी जल्दी क्यों टूट गई?",
      rewritten_text:
        "वार्ड 12 में स्टेशन रोड से बाज़ार चौक तक सड़क निर्माण के लिए जारी कार्य आदेश की प्रमाणित प्रति दें।",
      records_requested: ["कार्य आदेश की प्रमाणित प्रति"],
      reason: "'क्यों' के बजाय यह उस रिकॉर्ड की माँग करता है जो कार्यालय के पास है।",
      accepted: true,
    }),
    q(2, {
      original_text: "कितना पैसा खर्च हुआ?",
      rewritten_text:
        "इस काम की स्वीकृत राशि, अब तक किए गए भुगतान और मापन पुस्तिका की संबंधित प्रविष्टियों की प्रमाणित प्रतियाँ दें।",
      records_requested: ["स्वीकृत राशि का आदेश", "भुगतान का विवरण", "मापन पुस्तिका की प्रविष्टियाँ"],
      reason: "खर्च के सवाल को उन दस्तावेज़ों की माँग में बदला गया है जिनमें राशि दर्ज होती है।",
      accepted: true,
    }),
    q(3, {
      original_text: "क्या ठेकेदार ने काम ठीक से पूरा किया?",
      rewritten_text:
        "इस काम के कार्य पूर्णता प्रमाण पत्र और गुणवत्ता जाँच रिपोर्ट की प्रमाणित प्रतियाँ दें।",
      records_requested: ["कार्य पूर्णता प्रमाण पत्र", "गुणवत्ता जाँच रिपोर्ट"],
      reason: "राय पूछने के बजाय यह काम पूरा होने के रिकॉर्ड माँगता है।",
      accepted: false,
    }),
  ],
  flags: [],
  timeline: {
    status: "replied",
    filed_on: "2026-08-03",
    received_on: "2026-08-05",
    received_estimated: false,
    deadlines: [
      { kind: "pio_reply", due_on: "2026-09-04", due_at: null, estimated: false },
      { kind: "first_appeal", due_on: "2026-10-01", due_at: null, estimated: false },
    ],
  },
};

const passportDelay: Sample = {
  slug: "passport-delay",
  language: "en",
  concern:
    "I applied for a passport renewal three months ago. Police verification was done, but the passport has not been issued and nobody tells me why.",
  followUps: [
    {
      question: "Which passport office handles your application?",
      answer: "The Regional Passport Office in Sample City.",
    },
    {
      question: "When did you apply, and do you have the file number?",
      answer: "In July 2026. Yes, I have the file number.",
    },
    { question: "Do you want the copies by post or by email?", answer: "By post." },
  ],
  authority: {
    name: "Regional Passport Office, Sample City",
    designation: "Central Public Information Officer",
    address: "Regional Passport Office,\n4th Floor, Sample Bhavan,\nSample City",
  },
  applicant: { name: "Arjun Mehta (fictional name)", place: "Sample City" },
  questions: [
    q(1, {
      original_text: "Why is my passport delayed?",
      rewritten_text:
        "Provide the status record of my passport application (file number as given in the application), showing the date it moved through each stage of processing.",
      records_requested: ["Status record of the application", "Date of each processing stage"],
      reason: "Asks for the movement record the office keeps, instead of a reason for the delay.",
      accepted: true,
    }),
    q(2, {
      original_text: "Who is sitting on my file?",
      rewritten_text:
        "Provide copies of the file notings on my application, showing the designation of each officer who handled it and the date.",
      records_requested: ["File notings on the application"],
      reason: "Asks for file notings by designation, not for an officer's personal details.",
      accepted: true,
    }),
    q(3, {
      original_text: "When will I get my passport?",
      rewritten_text:
        "Provide a copy of the rules or circular that set the time limit for issuing a passport after police verification.",
      records_requested: ["Rules or circular on processing time"],
      reason: "A future date is a guess; the rule that sets the time limit is a record.",
      accepted: false,
    }),
  ],
  flags: [{ code: "opinion_ask", severity: "warn", question: 2, basis: null, under_challenge: false }],
  timeline: {
    status: "deemed_refused",
    filed_on: "2026-08-20",
    received_on: "2026-08-20",
    received_estimated: false,
    deadlines: [
      { kind: "pio_reply", due_on: "2026-09-19", due_at: null, estimated: false },
      { kind: "first_appeal", due_on: "2026-10-19", due_at: null, estimated: false },
    ],
  },
};

export const SAMPLES: Record<SampleSlug, Sample> = {
  "answer-sheet": answerSheet,
  "ward-road": wardRoad,
  "passport-delay": passportDelay,
};

export function isSampleSlug(value: string): value is SampleSlug {
  return (SAMPLE_SLUGS as readonly string[]).includes(value);
}
