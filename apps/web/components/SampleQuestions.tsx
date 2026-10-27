"use client";

import { useState } from "react";
import { QuestionCard } from "./QuestionCard";
import type { Question } from "@/lib/types";

/** Accept and Edit work on the sample questions, but only in this page's memory. */
export function SampleQuestions({ questions, language }: { questions: Question[]; language: string }) {
  const [items, setItems] = useState(questions);
  const patch = (id: string, fields: Partial<Question>) =>
    setItems((current) => current.map((q) => (q.id === id ? { ...q, ...fields } : q)));

  return (
    <ol className="space-y-4">
      {items.map((q, i) => (
        <li key={q.id}>
          <QuestionCard
            question={q}
            number={i + 1}
            contentLang={language}
            onAccept={() => patch(q.id, { accepted: true })}
            onSave={(text) =>
              patch(q.id, {
                rewritten_text: text,
                accepted: true,
                personal_information: false,
                suggestion: null,
              })
            }
          />
        </li>
      ))}
    </ol>
  );
}
