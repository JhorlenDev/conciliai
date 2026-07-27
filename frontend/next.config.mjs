import { resolve } from "node:path";

process.loadEnvFile(resolve(import.meta.dirname, "../.env"));

export default {};
