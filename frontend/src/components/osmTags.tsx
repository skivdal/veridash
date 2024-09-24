import useBackend, { SourceResponse } from "@/useBackend";

export default function OsmTags({ videoId }: { videoId: string | undefined }) {
  const data = useBackend<SourceResponse>(videoId, "osmtags");

  return (
    <div>
      Use the survey: <a href="https://forms.gle/zgX2bihHTo5NGdN38" className="font-medium text-blue-600 dark:text-blue-500 hover:underline">https://forms.gle/zgX2bihHTo5NGdN38</a> <br />

      Or scan the code:
      <img style={{ maxHeight: "200px", }} src="/survey-qr.jpg"></img>
    </div>
  );
}

