// English UI strings. This file defines the shape every other language must match (see
// messages/types.ts). Placeholders use {name} and are filled by format() in lib/i18n-core.ts.
// No fee, deadline or section number may appear here: those come from the API at run time.

export const en = {
  meta: {
    title: "UnSeal: RTI applications in English, Hindi and Tamil",
    description:
      "Turn your concern into a filing-ready RTI application, then track every deadline.",
  },
  common: {
    appName: "UnSeal",
    footer: "Prepared with UnSeal. Not legal advice.",
    footerLocal: "",
    footerNote:
      "UnSeal is an independent tool. It is not a government service.",
    skipToContent: "Skip to main content",
    chooseLanguage: "Choose language",
    mainNav: "Main",
    nav: {
      newCase: "New case",
      myCases: "My cases",
      samples: "Samples",
      myData: "My data",
    },
    loading: "Loading...",
    retry: "Try again",
    cancel: "Cancel",
    back: "Back",
    continue: "Continue",
    save: "Save",
    sample: "Sample",
    estimated: "estimated",
    optional: "optional",
    questionN: "Question {n}",
  },
  errors: {
    title: "Something needs your attention",
    busy: "UnSeal is busy right now. Please try again in a moment.",
    ask_user:
      "We could not understand that well enough. Please say it another way.",
    incomplete: "The answer was cut off before it finished. Please try again.",
    blocked:
      "The application cannot be made yet. Fix the items marked below first.",
    rate_limited:
      "That was a lot of requests in a short time. Please wait a minute and try again.",
    no_session:
      "Your session has ended, or it has not started on this device yet.",
    noSessionAction: "Start again",
    not_found: "We could not find that case. It may have been deleted.",
    notFoundAction: "Go to my cases",
    invalid: "Some details are not valid. Please check them and try again.",
    network:
      "Could not reach UnSeal. Check your internet connection and try again.",
    generic: "Something went wrong. Please try again.",
    wrong_status:
      "This step is not open for this case right now. Refresh the page to see where it stands.",
    invalid_grounds:
      "One of the reasons you chose does not apply to this case. For example, 'No reply in time' cannot be used once a reply has arrived.",
    invalid_payment_mode:
      "That payment mode is not accepted for this office. Please choose another one.",
    consent_required: "Please tick the box to agree before the letter is read.",
    unreadable_file:
      "We could not open that file. Upload a clear photo (JPG or PNG) or a PDF.",
    too_many_pages:
      "That PDF has more than {pages} pages. Upload only the pages of the reply letter.",
    length_required:
      "Your browser did not send the size of the file, so it was not accepted. Please try again, or use another browser.",
    too_large:
      "That file is larger than {mb} MB. Upload a smaller photo or PDF.",
  },
  landing: {
    eyebrow: "Right to Information, made simple",
    title: "Ask for the records, the right way.",
    pitch:
      "UnSeal turns your concern into a filing-ready RTI application in English, Hindi or Tamil, and keeps track of every deadline after you file.",
    start: "Start my application",
    starting: "Starting...",
    trySample: "Try a sample first",
    trySampleHint: "No sign-up and no personal details.",
    stepsTitle: "How it works",
    steps: [
      {
        title: "Describe the problem",
        body: "Write it in your own words, in English, Hindi or Tamil. We ask a few short questions.",
      },
      {
        title: "Review each question",
        body: "We reword 'why' questions into requests for records, which officers have to provide. You accept or edit each one.",
      },
      {
        title: "Download, file and track",
        body: "Get the application as a PDF with a filing checklist, then see every deadline on one timeline.",
      },
    ],
    demo: {
      beforeLabel: "Before",
      before: "Why is my result so low?",
      afterLabel: "After UnSeal",
      after:
        "Provide a certified copy of my evaluated answer script for Mathematics II, April 2026 session.",
    },
    actName: "Right to Information Act, 2005",
    actLine: "Every application is made under the {act}.",
  },
  consent: {
    title: "Before you start: your privacy",
    intro:
      "Please read this short notice. You can change your mind at any time.",
    items: [
      {
        title: "What we store",
        body: "Your description of the problem, your questions, the office you choose, your filing dates, and your name, postal address and phone number.",
      },
      {
        title: "Why we store it",
        body: "Only to prepare your application and to remind you of your deadlines. Nothing else.",
      },
      {
        title: "How it is protected",
        body: "Your name, address and phone number are encrypted. We never put them in web addresses, logs or analytics, and we never send them to the AI model. There are no ads and no tracking.",
      },
      {
        title: "Your control",
        body: "Download or delete all your data at any time from My data. Closed cases are deleted automatically after 180 days.",
      },
    ],
    principles:
      "We follow the principles of India's Digital Personal Data Protection Act, 2023: collect only what is needed, use it only for the purpose you agreed to, keep it safe, and erase it when you ask.",
    agree:
      "I have read this notice and I agree that UnSeal may store my data as described.",
    agreeRequired: "Please tick the box to agree before you start.",
  },
  flow: {
    title: "New application",
    noPersonalDetails: "Do not write your name, address or phone number here. You add those later, and they are never sent to the AI.",
    stepOf: "Step {n} of {total}",
    progress: "Progress",
    steps: {
      describe: "Describe",
      authority: "Office",
      questions: "Questions",
      applicant: "Your details",
      check: "Check and download",
      file: "File",
    },
    loadingCase: "Loading your application...",
    describe: {
      title: "What is the problem?",
      hint: "Say what happened, which office is involved and roughly when. Please do not include anyone else's personal details.",
      label: "Your concern",
      placeholder:
        "For example: my semester result looks wrong and I want to see my answer sheet.",
      languageLabel: "Language of the application",
      submit: "Continue",
      sending: "Reading your concern...",
      required: "Please describe your concern first.",
    },
    followUp: {
      title: "A few questions",
      hint: "Answer what you can. This helps us find the right office and records.",
      send: "Send answer",
      sending: "Reading your answer...",
      skip: "Continue without answering",
      ready: "We have enough to draft your application.",
      required:
        "Please answer at least one question, or continue without answering.",
    },
    authority: {
      title: "Where should this go?",
      hint: "Choose the office that holds the records, then check the address of its Public Information Officer.",
      suggested: "Suggested offices",
      searchLabel: "Search for an office",
      searchButton: "Search",
      searching: "Searching...",
      noResults: "No offices found. You can type the details below.",
      choose: "Use this office",
      chosen: "Selected",
      officer: "Officer: {designation}",
      online: "Accepts online applications",
      jurisdictionLabel: "Whose office is it?",
      nameLabel: "Name of the public authority",
      addressLabel: "Address of the Public Information Officer",
      addressHint: "Check this on the office's website or notice board.",
      viaApio: "I will file through an Assistant Public Information Officer",
      thirdParty: "The records are about a third party",
      lifeLiberty: "This concerns a person's life or liberty",
      lifeLibertyHint:
        "Tick this only if someone's life or freedom is at risk. The officer then has to reply much faster.",
      confirm: "Confirm office and address",
      saving: "Saving...",
      nameRequired: "Enter the name of the public authority.",
      addressRequired: "Enter the address of the Public Information Officer.",
      jurisdictionRequired: "Choose whose office it is.",
    },
    questions: {
      title: "Your questions",
      hint: "Write each thing you want to know. We suggest wording that asks for records, because officers must give records, not opinions.",
      addLabel: "New question",
      addButton: "Add question",
      adding: "Rewording your question...",
      suggestionsTitle: "Ideas from your description",
      useSuggestion: "Use: {text}",
      empty: "No questions yet. Add your first question above.",
      acceptAll: "Accept or edit every question to continue.",
      required: "Write a question first.",
    },
    applicant: {
      title: "Your details",
      hint: "These are printed only on your application. They are encrypted, and we will not show them here again.",
      name: "Full name",
      address: "Postal address",
      addressHint: "The officer will send the reply to this address.",
      phone: "Phone number",
      bpl: "I belong to a family below the poverty line (BPL)",
      bplHint:
        "Below-poverty-line applicants pay no fee. Attach a copy of your BPL certificate when you file.",
      save: "Save my details",
      saving: "Saving...",
      saved:
        "Your details are saved. For your privacy, we do not show them again.",
      replace: "Replace my details",
      nameRequired: "Enter your name.",
      addressRequired: "Enter your postal address.",
      phoneInvalid: "Enter a valid phone number, or leave it empty.",
    },
    check: {
      title: "Check and download",
      checking: "Checking your application...",
      noFlags: "No problems found.",
      blockedNote:
        "Fix the items marked 'Must fix' to download your application.",
      paymentModeLabel: "How will you pay the fee?",
      placeLabel: "Place (town or city)",
      placeRequired: "Enter the town or city where you sign the application.",
      download: "Download application (PDF)",
      downloading: "Preparing your PDF...",
      downloaded:
        "Your application is downloaded. Print it, sign it and send it.",
      editAuthority: "Change office or address",
      editApplicant: "Change your details",
      editQuestions: "Change questions",
      next: "I am ready to file",
    },
    file: {
      title: "Have you filed it?",
      hint: "Tell us when and how you sent it. We then work out your deadlines.",
      filedOn: "Date you filed it",
      mode: "How you filed it",
      receivedOn: "Date the office received it",
      receivedHint:
        "Leave this empty if you sent it by post and do not know yet. We will estimate it.",
      submit: "I have filed it",
      saving: "Saving...",
      dateRequired: "Enter the date you filed it.",
    },
  },
  flags: {
    title: "Checks",
    severity: {
      block: "Must fix",
      warn: "Worth checking",
    },
    codes: {
      missing_pio_address:
        "Add the address of the Public Information Officer. The application cannot be made without it.",
      missing_applicant_address:
        "Add your postal address. The officer needs it to send the reply.",
      no_questions: "Add at least one question.",
      over_word_limit:
        "Your application is longer than the recommended length. It cannot be rejected for length alone, but a shorter one is easier to answer.",
      personal_information:
        "This may ask for another person's personal information, which is exempt from disclosure. Ask for totals or anonymised records instead.",
      opinion_ask:
        "This asks for an opinion or a reason. Officers only have to give records, so ask for documents instead.",
    },
    unknown: "Please check this item ({code}).",
    forQuestion: "Question {n}",
    basis: "Basis: {basis}",
    underChallenge:
      "This rule is being challenged in the Supreme Court and may change.",
  },
  question: {
    original: "You wrote",
    rewritten: "Suggested wording",
    records: "Records this asks for",
    reason: "Why we changed it",
    accept: "Accept",
    acceptLabel: "Accept question {n}",
    accepted: "Accepted",
    edit: "Edit",
    editLabel: "Edit question {n}",
    editField: "Your wording for question {n}",
    save: "Save",
    saveLabel: "Save question {n}",
    cancel: "Cancel",
    remove: "Remove",
    removeLabel: "Remove question {n}",
    emptyError: "Write the question before saving.",
    personalWarning:
      "This may ask for another person's personal information, which is exempt from disclosure.",
    suggestion: "Try this instead:",
    useSuggestion: "Use this wording",
    useSuggestionLabel: "Use this wording for question {n}",
    refused: "We could not reword this one safely.",
  },
  checklist: {
    title: "Filing checklist",
    fee: "Application fee: Rs {fee}",
    feeBpl: "No fee if you are below the poverty line (BPL).",
    feeBplCertificate: "Attach a copy of your BPL certificate.",
    copyFee: "Copies of records: Rs {fee} per page.",
    paymentModes: "Accepted ways to pay",
    where: "Where to send it",
    channels: "Ways to file",
    proof: "What to keep as proof",
    proofItems: [
      "A copy of the signed application.",
      "The fee receipt, or a copy of the draft, cheque or stamp you used.",
      "The postal receipt and tracking number, or the acknowledgement if you file in person or online.",
    ],
    wordLimit:
      "Try to keep it to about {limit} words. It cannot be rejected for length alone.",
    confirm:
      "Rules can change. Confirm the fee and the payment mode with the authority before you file.",
    recheck:
      "Some of these rules were last checked a while ago. Please confirm them with the authority.",
    sources: "Sources",
    checkedOn: "checked {date}",
    loading: "Loading the filing rules...",
  },
  paymentModes: {
    cash: "Cash",
    demand_draft: "Demand draft",
    bankers_cheque: "Banker's cheque",
    indian_postal_order: "Indian Postal Order",
    electronic: "Electronic payment",
    court_fee_stamp: "Court fee stamp",
    postal_money_order: "Postal money order",
  },
  filingChannels: {
    rti_online: "RTI Online portal",
    post: "By post",
    in_person: "In person",
  },
  jurisdictions: {
    central: "Central Government",
    tamil_nadu: "Government of Tamil Nadu",
  },
  timeline: {
    title: "Timeline",
    stateLabels: {
      done: "Done",
      current: "Now",
      upcoming: "Later",
    },
    statuses: {
      draft: "Draft",
      filed: "Filed",
      reply_due: "Reply due",
      replied: "Reply received",
      deemed_refused: "No reply in time",
      reply_or_refused: "Reply received, or no reply in time",
      appealed: "Appealed",
      closed: "Closed",
    },
    descriptions: {
      draft: "You are preparing the application.",
      filed: "You have sent the application.",
      reply_due: "Waiting for the officer's reply.",
      replied:
        "The officer has replied. If the reply is incomplete, you can file a first appeal.",
      deemed_refused:
        "The officer did not reply in time. This counts as a refusal, and you can file a first appeal.",
      reply_or_refused: "The officer replies, or the time to reply runs out.",
      appealed: "You have filed an appeal.",
      closed: "This case is closed.",
    },
    unknownStatus:
      "Status not recognised ({status}). Please refresh, or contact us if this stays.",
    deadlines: {
      pio_reply: "Reply due from the Public Information Officer",
      first_appeal: "Last day to file the first appeal",
      faa_decision: "Appellate authority's decision due",
      second_appeal: "Last day to file the second appeal",
    },
    unknownDeadline: "Deadline ({kind})",
    filedOn: "Filed on {date}",
    receivedOn: "Received by the office on {date}",
    estimatedHelp:
      "Estimated: the date the office received your application is not known, so we added time for delivery.",
    replyReceivedOn: "Reply received on {date}",
    appealFiledOn: "Appeal filed on {date}",
  },
  dashboard: {
    title: "My cases",
    newCase: "Start a new case",
    empty: "You have no cases yet.",
    noSession: "There are no cases on this device yet.",
    noAuthority: "Office not chosen yet",
    nextDeadline: "Next deadline",
    noDeadline: "No deadlines yet",
    started: "Started {date}",
    open: "Open case",
    openLabel: "Open case: {name}",
    status: "Status",
  },
  caseDetail: {
    title: "Your case",
    back: "Back to my cases",
    continueDraft: "Continue your application",
    actionsTitle: "What happened next?",
    replyTitle: "Record the reply",
    replyDate: "Date you received the reply",
    replySave: "Save reply date",
    replySaving: "Saving...",
    replyRequired: "Enter the date you received the reply.",
    close: "Close this case",
    closeConfirm:
      "Close this case? You can still see it here. Closed cases are deleted automatically after 180 days.",
    closeYes: "Yes, close it",
    closing: "Closing...",
    delete: "Delete this case",
    deleteConfirm:
      "Delete this case and everything in it? This cannot be undone.",
    deleteYes: "Yes, delete it",
    deleting: "Deleting...",
    authority: "Office",
    noAuthority: "Not chosen yet",
    receiptTitle: "When did the office receive it?",
    receiptHint:
      "Check the postal tracking page or the acknowledgement you were given. Once you enter the actual date, your deadlines count from it and are no longer estimates.",
    receiptLabel: "Date the office received it",
    receiptSave: "Save received date",
    receiptSaving: "Saving...",
    receiptRequired: "Enter the date the office received it.",
    receiptSaved: "Saved. Your deadlines now count from this date.",
    replyManualHint:
      "No photo of the letter? Enter the date you received the reply.",
  },
  myData: {
    title: "My data",
    intro:
      "You are in control of your data. Download a copy, or delete everything.",
    exportTitle: "Export my data",
    exportBody:
      "Download one file with all your cases and the details you entered. It includes your name and address, so keep it safe.",
    exportButton: "Export my data",
    exportConfirm:
      "The file will contain your name and address in plain text. Download it now?",
    exportYes: "Yes, download",
    exporting: "Preparing your file...",
    exported: "Your file is downloaded.",
    deleteTitle: "Delete my data",
    deleteBody:
      "This deletes every case, question, date and personal detail you saved, and ends your session on this device.",
    deleteButton: "Delete my data",
    deleteConfirm: "This cannot be undone. Delete everything now?",
    deleteYes: "Yes, delete everything",
    deleting: "Deleting...",
    deleted: "All your data has been deleted.",
    noSession: "There is no data from this device to export or delete.",
  },
  samples: {
    title: "Sample cases",
    intro:
      "Walk through UnSeal with three made-up cases. Nothing is sent or saved, and every applicant is fictional.",
    banner: "Sample: a fictional case. Nothing here is sent or saved.",
    open: "Walk through this sample",
    openLabel: "Walk through this sample: {title}",
    caseLanguage: "Application in {language}",
    concern: "The concern",
    followUps: "Follow-up questions",
    answer: "Answer",
    authority: "Office and address",
    applicant: "Applicant (fictional)",
    questions: "Questions after review",
    tryAccept: "Try Accept and Edit: changes stay on this page only.",
    checks: "Checks before download",
    checklist: "Filing checklist",
    checklistNote:
      "In a real case, the fee, payment modes and filing channels come from the official rules for the office you choose.",
    timeline: "Timeline after filing",
    timelineNote: "Dates in this sample are made up.",
    startReal: "Start a real application",
    backToSamples: "All samples",
    cases: {
      "answer-sheet": {
        title: "A student's answer sheet",
        summary:
          "A student asks a state university for a copy of an evaluated answer sheet.",
      },
      "ward-road": {
        title: "A broken ward road",
        summary:
          "A resident asks a municipal corporation for the records behind a road repair.",
      },
      "passport-delay": {
        title: "A delayed passport",
        summary:
          "An applicant asks a passport office for the status records of a delayed application.",
      },
    },
  },
  replyReader: {
    title: "Read the reply letter",
    intro:
      "Got a reply from the officer? Upload a photo or PDF of the letter. UnSeal lists what was given, refused or transferred, and suggests reasons for an appeal.",
    fileLabel: "Photo or PDF of the reply letter",
    fileHint: "JPG, PNG or PDF, up to {mb} MB and {pages} pages.",
    fileRequired: "Choose a photo or PDF of the letter first.",
    consent:
      "This letter has personal details. I agree that UnSeal sends it to the AI model only to read it. It is not stored.",
    read: "Read the letter",
    reading: "Reading the letter...",
    resultTitle: "What the letter says",
    checkNote:
      "An AI model read this letter and can make mistakes. Check it against the letter.",
    letterDate: "Date on the letter",
    letterDateUnknown: "Not readable",
    points: "Answers to your questions",
    point: "Point {n}",
    sectionCited: "Section cited: {section}",
    noPoints: "No numbered answers could be read.",
    feeDemanded: "The letter asks for a further fee.",
    noFee: "No further fee is asked for.",
    transferredTo: "Transferred to: {office}",
    statuses: {
      given: "Given",
      refused: "Refused",
      partial: "Partly given",
      transferred: "Transferred",
      unclear: "Not clear",
    },
    receivedTitle: "When did you receive this letter?",
    receivedHint:
      "The date on the letter is filled in. Change it if the letter reached you on a different day.",
    receivedLabel: "Date you received the letter",
    receivedRequired: "Enter the date you received the letter.",
    save: "Save and continue",
    saving: "Saving...",
    appealNext:
      "Next: the first appeal below has the suggested reasons ticked.",
  },
  appeal: {
    title: "First appeal",
    intro:
      "If there was no reply in time, or the reply is incomplete or refuses the request, you can appeal to the First Appellate Authority of the same office.",
    groundsLegend: "Why are you appealing?",
    groundsHint: "Tick every reason that applies.",
    grounds: {
      no_reply: "No reply in time",
      incomplete: "The reply is incomplete or not what I asked for",
      refused: "The request was refused",
      fee_demanded: "A fee was demanded that should not be payable",
    },
    suggestedNote:
      "We ticked the reasons the reply letter suggests. Check them.",
    groundsRequired: "Choose at least one reason.",
    addressedTo: "Addressed to",
    faaTitle: "First Appellate Authority",
    faaLabel: "Address of the First Appellate Authority",
    faaHint:
      "Usually the same office as the Public Information Officer. Check the address on the reply letter or the office's website.",
    faaConfirm: "I have checked this address.",
    faaRequired: "Enter the address of the First Appellate Authority.",
    faaConfirmRequired: "Please confirm that you have checked the address.",
    detailsLabel: "Anything else to add (optional)",
    detailsHint: "In your own words: what was missing or wrong.",
    delayLabel: "Reason for the delay",
    delayHint:
      "The last day for the first appeal has passed. The appellate authority may still accept a late appeal if you explain the delay.",
    delayRequired: "Explain why the appeal is late.",
    download: "Download first appeal (PDF)",
    downloading: "Preparing your appeal...",
    downloaded:
      "Your first appeal is downloaded. Print it, sign it and send it to the First Appellate Authority.",
    filingTitle: "Have you filed the appeal?",
    filedOn: "Date you filed the appeal",
    receivedOn: "Date the appellate authority received it",
    receivedHint: "Leave this empty if you do not know yet.",
    fileSubmit: "I have filed the appeal",
    filing: "Saving...",
    filedNote:
      "Your appeal was filed on {date}. You can download it again if you need another copy.",
    dateRequired: "Enter the date you filed the appeal.",
  },
  notFound: {
    title: "Page not found",
    body: "This page does not exist.",
    home: "Go to the home page",
  },
};
