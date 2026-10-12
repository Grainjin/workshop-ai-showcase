import type { getStateFromPath } from "@react-navigation/native";

type PathParser = typeof getStateFromPath;

// Application limit for the raw pathname + query, in UTF-16 code units.
const MAX_RAW_PATH_LENGTH = 4096;

export function createGuardedPathParser(parser: PathParser): PathParser {
  return (path, options) => {
    if (typeof path !== "string" || path.length > MAX_RAW_PATH_LENGTH) {
      return undefined;
    }

    try {
      // Validate only: never pass decoded separators or query values onward.
      // Built-in decoding rejects malformed escapes/UTF-8 before the dependency.
      decodeURIComponent(path);
    } catch {
      return undefined;
    }

    return parser(path, options);
  };
}
