package mcp

import (
  "encoding/json"
  "github.com/invopop/jsonschema"
  "github.com/mark3labs/mcp-go/mcp"
)

func makeInputSchema(
  schema mcp.ToolInputSchema,
) (*jsonschema.Schema, error) {
  var inputSchema jsonschema.Schema
  inputSchema.Required = schema.Required
  inputSchema.Type = schema.Type
  inputSchema.Properties = jsonschema.NewProperties()

  for key, value := range schema.Properties {
    var obj jsonschema.Schema
    rawValue, err := json.Marshal(value)
    if err != nil {
      return nil, err
    }
    if err := obj.UnmarshalJSON(rawValue); err != nil {
      return nil, err
    }
    inputSchema.Properties.Set(key, &obj)
  }

  return &inputSchema, nil
}
