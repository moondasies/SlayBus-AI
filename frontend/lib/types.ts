export type QuestionType = "mcq" | "fill_blank" | "true_false" | "short_answer" | "long_answer" | "case_based";
export type Difficulty = "easy" | "medium" | "hard";
export type PaperType = "question_paper" | "worksheet" | "quiz";

export interface Profile {
  id: string;
  email: string | null;
  name: string | null;
  school: string | null;
  board: string | null;
  subjects: string[];
  classes: string[];
  onboarded: boolean;
  stats: { textbooks: number; papers: number; questions: number };
}

export interface Chapter {
  id: string;
  number: number;
  title: string;
  start_page: number;
  end_page: number;
  chunk_count: number;
}

export interface Textbook {
  id: string;
  title: string;
  subject: string | null;
  class_level: string | null;
  board: string | null;
  status: "uploaded" | "processing" | "ready" | "failed";
  progress: number;
  error_message: string | null;
  page_count: number | null;
  chapter_method: string | null;
  chapter_count: number;
  created_at: string;
  chapters?: Chapter[];
}

export interface SectionSpec {
  name: string;
  type: QuestionType;
  count: number;
  marks_each: number;
  instructions?: string | null;
}

export interface Question {
  id: string;
  paper_id: string | null;
  chapter_id: string | null;
  chapter_title: string | null;
  chapter_number: number | null;
  section: string;
  order_index: number;
  type: QuestionType;
  difficulty: Difficulty;
  marks: number;
  question_text: string;
  options: string[] | null;
  answer: string | null;
  explanation: string | null;
  marking_points: string[] | null;
  source_pages: number[];
  created_at: string;
}

export interface PaperSummary {
  id: string;
  title: string;
  paper_type: PaperType;
  status: "generating" | "ready" | "failed";
  error_message: string | null;
  total_marks: number | null;
  duration_min: number | null;
  created_at: string;
  textbook_id: string | null;
  textbook_title: string | null;
  question_count: number;
}

export interface Paper extends PaperSummary {
  config: {
    class_level?: string | null;
    subject?: string | null;
    board?: string | null;
    instructions?: string | null;
    sections: SectionSpec[];
    chapter_ids: string[];
  };
  sections: SectionSpec[];
  questions: Question[];
}

export interface SourceChunk {
  id: string;
  page: number;
  content: string;
  chapter_title: string | null;
}

export const TYPE_LABELS: Record<QuestionType, string> = {
  mcq: "Multiple choice",
  fill_blank: "Fill in the blank",
  true_false: "True / False",
  short_answer: "Short answer",
  long_answer: "Long answer",
  case_based: "Case-based",
};

export const PAPER_TYPE_LABELS: Record<PaperType, string> = {
  question_paper: "Question paper",
  worksheet: "Worksheet",
  quiz: "Quick quiz",
};
