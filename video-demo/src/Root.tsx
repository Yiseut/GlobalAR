import {Composition} from "remotion";
import {GlobalAestheticsDemo} from "./GlobalAestheticsDemo";

export const RemotionRoot = () => {
  return (
    <Composition
      id="GlobalAestheticsDemo"
      component={GlobalAestheticsDemo}
      durationInFrames={60 * 30}
      fps={30}
      width={1920}
      height={1080}
    />
  );
};
