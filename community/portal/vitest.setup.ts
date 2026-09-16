import '@testing-library/jest-dom';

// jsdom 没有 fetch, 用 undici polyfill
import { fetch, Headers, Request, Response } from 'undici';
if (!globalThis.fetch) {
  // @ts-ignore
  globalThis.fetch = fetch;
  // @ts-ignore
  globalThis.Headers = Headers;
  // @ts-ignore
  globalThis.Request = Request;
  // @ts-ignore
  globalThis.Response = Response;
}

// jsdom 没有 TextEncoder/TextDecoder (Next.js 内部用)
import { TextEncoder, TextDecoder } from 'util';
if (!globalThis.TextEncoder) {
  // @ts-ignore
  globalThis.TextEncoder = TextEncoder;
  // @ts-ignore
  globalThis.TextDecoder = TextDecoder;
}
