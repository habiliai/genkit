// Copyright 2025 Google LLC
// SPDX-License-Identifier: Apache-2.0

package main

import (
	"context"
	"errors"
	"fmt"
	"os"
	"time"

	"github.com/firebase/genkit/go/ai"
	"github.com/firebase/genkit/go/genkit"
	"github.com/firebase/genkit/go/plugins/vertexai"
)

// lotrQuestionInput is a question about the LOTR chapters.
type lotrQuestionInput struct {
	Question string `json:"question"`
	FilePath string `json:"path"`
}

func main() {
	projectID := os.Getenv("GCLOUD_PROJECT")
	if projectID == "" {
		fmt.Println("GCLOUD_PROJECT environment variable not set")
		return
	}
	location := os.Getenv("GCLOUD_LOCATION")
	if location == "" {
		fmt.Println("GCLOUD_LOCATION environment variable not set")
		return
	}
	ctx := context.Background()
	g, err := genkit.Init(ctx, genkit.WithDefaultModel("vertexai/gemini-1.5-flash"))
	if err != nil {
		fmt.Println(err)
	}
	err = vertexai.Init(ctx, g, &vertexai.Config{
		ProjectID: projectID,
		Location:  location,
	})
	if err != nil {
		fmt.Println(err)
	}

	genkit.DefineFlow(g, "lotr-VertexAI", func(ctx context.Context, input *lotrQuestionInput) (string, error) {
		prompt := "What is the text I provided you with?"
		if input == nil {
			return "", errors.New("empty flow input, provide at least a source file to read")
		}
		if len(input.Question) > 0 {
			prompt = input.Question
		}

		textContent, err := os.ReadFile(input.FilePath)
		if err != nil {
			return "", err
		}

		resp, err := genkit.Generate(ctx, g, ai.WithConfig(&ai.GenerationCommonConfig{
			Temperature: 1,
			TTL:         time.Hour,
			Version:     "gemini-1.5-flash-001",
		}),
			ai.WithTextPrompt(prompt),
			ai.WithMessages(ai.NewUserMessage(
				ai.NewTextPart(string(textContent)))))
		if err != nil {
			return "", nil
		}

		text := resp.Text()

		fmt.Printf("%#v", resp.Usage)
		return text, nil
	})

	<-ctx.Done()
}
