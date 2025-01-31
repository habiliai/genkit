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

import { GenkitMetric, genkitEvalRef } from '@genkit-ai/evaluator';
import { z } from 'genkit';
import {
  type Dataset,
  type EvalResponse,
  EvalResponseSchema,
} from 'genkit/evaluator';
import { ai } from './genkit';

const DOG_DATASET: Dataset = require('../data/dogfacts.json');

// Run this flow to programatically execute the evaluator on the dog dataset.
export const dogFactsEvalFlow = ai.defineFlow(
  {
    name: 'dogFactsEval',
    inputSchema: z.void(),
    outputSchema: z.array(EvalResponseSchema),
  },
  async (): Promise<Array<EvalResponse>> => {
    return await ai.evaluate({
      evaluator: genkitEvalRef(GenkitMetric.FAITHFULNESS),
      dataset: DOG_DATASET,
      evalRunId: 'my-dog-eval',
    });
  }
);
