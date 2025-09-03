import CaseView from "@/components/CaseView";

interface PageProps {
  params: {
    id: string;
  };
}

export default function CasePage({ params }: PageProps) {
  return <CaseView caseId={params.id} />;
}
