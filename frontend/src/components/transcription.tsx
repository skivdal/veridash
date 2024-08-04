import useBackend, { TranscriptionResponse } from "@/useBackend";
import ISO6391 from 'iso-639-1';

export default function Transcription({ videoId, onScrub: handleScrub }: {
  videoId: string | undefined,
  onScrub: (scrubTime: number) => void
}) {
  function secondsToTimecode(seconds: number) {
    return new Date(seconds * 1000).toISOString().slice(11, 19);
  }

  const data = useBackend<TranscriptionResponse>(videoId, "transcription");

  if ((data as TranscriptionResponse)?.transcription.language) {
    const d = data as TranscriptionResponse;
    if (d.transcription.segments.length === 0 || (d.transcription.segments.length == 1 && d.transcription.segments[0].no_speech_prob > 0.4)) {
      return (
        <div>
          Transcription/translation
          <p className="mt-2 text-gray-600 italic">There is probably no speech in this video</p>
        </div>
      );
    }

    return (
      <div className="h-full overflow-auto hover:overflow-scroll">
        Transcription ({ISO6391.getName(d.transcription.language)} - {d.transcription.language}):
        {
          d.transcription.segments
            .filter(x => x.no_speech_prob < 0.7)
            .map(x =>
              <p className="mb-2">
                <span
                  className="text-blue-400 underline hover:text-blue-600 hover:no-underline"
                  onClick={() => { handleScrub(x.start); }}
                >
                  {secondsToTimecode(x.start)}
                </span>
                <span> - {secondsToTimecode(x.end)}</span>

                <br />
                <span>{x.text}</span>

                {x.text_en ? (<>
                  <br />
                  <span className="text-gray-600">{x.text_en}</span>
                </>) : ""}
              </p>
            )
        }
      </div>
    )
  }

  return (
    <div>Transcription/translation</div>
  );
}

