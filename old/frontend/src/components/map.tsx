import { useEffect, useState } from "react";
import { MapContainer, TileLayer, Marker, Popup, useMap } from "react-leaflet";
import "leaflet/dist/leaflet.css";
// @ts-ignore
import "leaflet-defaulticon-compatibility";
import "leaflet-defaulticon-compatibility/dist/leaflet-defaulticon-compatibility.css";

import useBackend, { MapResponse } from "@/useBackend";

const RecenterMap = ({ lat, lng }: { lat: number, lng: number }) => {
  const map = useMap();
  map.setView([lat, lng]);
  return null;
};

export default function Map({ videoId }: { videoId: string | undefined }) {
  const data = useBackend<MapResponse>(videoId, "map");

  const [position, setPosition] = useState([60.39, 5.32]); // Default location: Bergen
  const [positionUpdated, setPositionUpdated] = useState(false);
  const [noPosition, setNoPosition] = useState(false);

  useEffect(() => {
    if (!data)
      return;

    const d = data as MapResponse;

    if (d.latlng) {
      setPosition(d.latlng);
      setPositionUpdated(true);
    }
    else if (d.latlng === null) {
      setNoPosition(true);
    }
  }, [data]);

  return (
    <div className="h-full">
      <p className="mb-2">Map</p>

      {noPosition ? (
        <p className="mb-2 text-gray-600 italic">Could not find any positional data</p>
      ) : ''}

      <MapContainer key={videoId || "default"} center={position} zoom={13} scrollWheelZoom={true} className="h-5/6">
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        {positionUpdated ? (
          <Marker position={position}>
            <Popup>
              Location according to metadata
            </Popup>
          </Marker>
        ) : ''}
        <RecenterMap lat={position[0]} lng={position[1]} />
      </MapContainer>
    </div>
  );
}
