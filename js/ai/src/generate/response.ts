/**
 * Copyright 2024 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

import { parseSchema } from '@genkit-ai/core/schema';
import {
  GenerationBlockedError,
  GenerationResponseError,
} from '../generate.js';
import { Message, type MessageParser } from '../message.js';
import type {
  GenerateRequest,
  GenerateResponseData,
  GenerationUsage,
  MessageData,
  ModelResponseData,
  ToolRequestPart,
} from '../model.js';

/**
 * GenerateResponse is the result from a `generate()` call and contains one or
 * more generated candidate messages.
 */
export class GenerateResponse<O = unknown> implements ModelResponseData {
  /** The generated message. */
  message?: Message<O>;
  /** The reason generation stopped for this request. */
  finishReason: ModelResponseData['finishReason'];
  /** Additional information about why the model stopped generating, if any. */
  finishMessage?: string;
  /** Usage information. */
  usage: GenerationUsage;
  /** Provider-specific response data. */
  custom: unknown;
  /** The request that generated this response. */
  request?: GenerateRequest;
  /** The parser for output parsing of this response. */
  parser?: MessageParser<O>;

  constructor(
    response: GenerateResponseData,
    options?: {
      request?: GenerateRequest;
      parser?: MessageParser<O>;
    }
  ) {
    // Check for candidates in addition to message for backwards compatibility.
    const generatedMessage =
      response.message || response.candidates?.[0]?.message;
    if (generatedMessage) {
      this.message = new Message<O>(generatedMessage, {
        parser: options?.parser,
      });
    }
    this.finishReason =
      response.finishReason || response.candidates?.[0]?.finishReason!;
    this.finishMessage =
      response.finishMessage || response.candidates?.[0]?.finishMessage;
    this.usage = response.usage || {};
    this.custom = response.custom || {};
    this.request = options?.request;
  }

  /**
   * Throws an error if the response does not contain valid output.
   */
  assertValid(): void {
    if (this.finishReason === 'blocked') {
      throw new GenerationBlockedError(
        this,
        `Generation blocked${this.finishMessage ? `: ${this.finishMessage}` : '.'}`
      );
    }

    if (!this.message) {
      throw new GenerationResponseError(
        this,
        `Model did not generate a message. Finish reason: '${this.finishReason}': ${this.finishMessage}`
      );
    }
  }

  /**
   * Throws an error if the response does not conform to expected schema.
   */
  assertValidSchema(request?: GenerateRequest): void {
    if (request?.output?.schema || this.request?.output?.schema) {
      const o = this.output;
      parseSchema(o, {
        jsonSchema: request?.output?.schema || this.request?.output?.schema,
      });
    }
  }

  isValid(request?: GenerateRequest): boolean {
    try {
      this.assertValid();
      this.assertValidSchema(request);
      return true;
    } catch (e) {
      return false;
    }
  }

  /**
   * If the generated message contains a `data` part, it is returned. Otherwise,
   * the `output()` method extracts the first valid JSON object or array from the text
   * contained in the selected candidate's message and returns it.
   *
   * @returns The structured output contained in the selected candidate.
   */
  get output(): O | null {
    return this.message?.output || null;
  }

  /**
   * Concatenates all `text` parts present in the generated message with no delimiter.
   * @returns A string of all concatenated text parts.
   */
  get text(): string {
    return this.message?.text || '';
  }

  /**
   * Returns the first detected media part in the generated message. Useful for
   * extracting (for example) an image from a generation expected to create one.
   * @returns The first detected `media` part in the candidate.
   */
  get media(): { url: string; contentType?: string } | null {
    return this.message?.media || null;
  }

  /**
   * Returns the first detected `data` part of the generated message.
   * @returns The first `data` part detected in the candidate (if any).
   */
  get data(): O | null {
    return this.message?.data || null;
  }

  /**
   * Returns all tool request found in the generated message.
   * @returns Array of all tool request found in the candidate.
   */
  get toolRequests(): ToolRequestPart[] {
    return this.message?.toolRequests || [];
  }

  /**
   * Returns all tool requests annotated as interrupts found in the generated message.
   * @returns A list of ToolRequestParts.
   */
  get interrupts(): ToolRequestPart[] {
    return this.message?.interrupts || [];
  }

  /**
   * Appends the message generated by the selected candidate to the messages already
   * present in the generation request. The result of this method can be safely
   * serialized to JSON for persistence in a database.
   * @param index The candidate index to utilize during conversion, defaults to first candidate.
   * @returns A serializable list of messages compatible with `generate({history})`.
   */
  get messages(): MessageData[] {
    if (!this.request)
      throw new Error(
        "Can't construct history for response without request reference."
      );
    if (!this.message)
      throw new Error(
        "Can't construct history for response without generated message."
      );
    return [...this.request?.messages, this.message.toJSON()];
  }

  get raw(): unknown {
    return this.raw ?? this.custom;
  }

  toJSON(): ModelResponseData {
    const out = {
      message: this.message?.toJSON(),
      finishReason: this.finishReason,
      finishMessage: this.finishMessage,
      usage: this.usage,
      custom: (this.custom as { toJSON?: () => any }).toJSON?.() || this.custom,
      request: this.request,
    };
    if (!out.finishMessage) delete out.finishMessage;
    if (!out.request) delete out.request;
    return out;
  }
}
