import {Composition} from "remotion";
import {GlobalAestheticsGlobeDemo} from "./GlobalAestheticsGlobeDemo";

export const RemotionRoot = () => {
  return (
    <Composition
      id="GlobalAestheticsGlobeDemo"
      component={GlobalAestheticsGlobeDemo}
      durationInFrames={113 * 30}
      fps={30}
      width={1920}
      height={1080}
    />
  );
};
