import {Config} from '@remotion/cli/config';

// H.264 MP4 at good quality; scripts/scripture.py adds a loudness pass afterwards.
Config.setVideoImageFormat('jpeg');
Config.setJpegQuality(92);
Config.setCodec('h264');
Config.setCrf(18);
Config.setPixelFormat('yuv420p');
