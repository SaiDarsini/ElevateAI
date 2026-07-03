export interface TargetCompany {
  id: string;
  name: string;
  role: string;
  matchScore: number;
  reason: string;
  location: string;
  salary: string;
}

export interface InterviewQuestion {
  id: string;
  companyName: string;
  question: string;
  category: string;
  difficulty: "Easy" | "Medium" | "Hard";
  tips: string;
  sampleAnswer: string;
}

export interface DayAction {
  day: string;
  title: string;
  tasks: string[];
  focusArea: string;
}

export interface ResumeProfile {
  id: string;
  label: string;
  candidateName: string;
  jobTitle: string;
  atsScore: number;
  pdfFileName: string;
  missingSkills: string[];
  targetCompanies: TargetCompany[];
  interviewQuestions: InterviewQuestion[];
  sevenDayPlan: DayAction[];
}
