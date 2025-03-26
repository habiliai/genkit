package mcp

import (
  "context"
  "encoding/json"
  "fmt"
  "github.com/firebase/genkit/go/ai"
  "github.com/firebase/genkit/go/core"
  "github.com/firebase/genkit/go/internal/action"
  "github.com/firebase/genkit/go/internal/base"
  "github.com/firebase/genkit/go/internal/registry"
  mcpclient "github.com/mark3labs/mcp-go/client"
  "github.com/mark3labs/mcp-go/mcp"
  "github.com/mitchellh/mapstructure"
  "strings"
)

const provider = "mcp"

type tool struct {
  action action.Action
}

func (t *tool) Action() action.Action {
  return t.action
}

func (t *tool) Definition() *ai.ToolDefinition {
  act := t.Action()
  desc := act.Desc()
  return &ai.ToolDefinition{
    Name:         desc.Metadata["name"].(string),
    Description:  desc.Metadata["description"].(string),
    InputSchema:  base.SchemaAsMap(desc.InputSchema),
    OutputSchema: base.SchemaAsMap(desc.OutputSchema),
  }
}

func (t *tool) RunRaw(ctx context.Context, input map[string]any) (r any, err error) {
  act := t.Action()

  mi, err := json.Marshal(input)
  if err != nil {
    return r, fmt.Errorf("error marshalling tool input for %v: %v", t.Definition().Name, err)
  }
  output, err := act.RunJSON(ctx, mi, nil)
  if err != nil {
    return r, fmt.Errorf("error calling tool %v: %v", t.Definition().Name, err)
  }

  var uo any
  err = json.Unmarshal(output, &uo)
  if err != nil {
    return nil, fmt.Errorf("error parsing tool input for %v: %v", t.Definition().Name, err)
  }
  return uo, nil
}

type Content struct {
  Text          string `json:"text,omitempty"`
  ImageData     string `json:"image_data,omitempty"`
  ImageMIMEType string `json:"image_mimeType,omitempty"`
}

// DefineTool defines a tool function.
func DefineTool(mcpClient mcpclient.MCPClient, mcpServerName string, mcpTool mcp.Tool) (ai.Tool, error) {
  metadata := make(map[string]any)
  metadata["type"] = "tool"
  metadata["name"] = mcpTool.Name
  metadata["description"] = mcpTool.Description

  schema, err := makeInputSchema(mcpTool.InputSchema)
  if err != nil {
    return nil, err
  }
  toolAction := core.DefineActionWithInputSchema(provider, mcpServerName+"/"+mcpTool.Name, "tool", metadata, schema, func(ctx context.Context, input any) (out Content, err error) {
    if err = mcpClient.Ping(ctx); err != nil {
      return
    }

    req := mcp.CallToolRequest{
      Request: mcp.Request{
        Method: "tools/call",
      },
    }
    req.Params.Name = mcpTool.Name
    if input != nil {
      if err = mapstructure.Decode(input, &req.Params.Arguments); err != nil {
        return
      }
    }

    var result *mcp.CallToolResult
    if result, err = mcpClient.CallTool(ctx, req); err != nil {
      return
    }

    for _, cont := range result.Content {
      if c, ok := cont.(mcp.TextContent); ok {
        out.Text = c.Text
      } else if c, ok := cont.(mcp.ImageContent); ok {
        out.ImageData = c.Data
        out.ImageMIMEType = c.MIMEType
      }
    }

    if result.IsError {
      errorMsg := fmt.Sprintf("error calling tool %v", mcpTool.Name)
      if out.Text != "" {
        errorMsg += fmt.Sprintf(": %s", out.Text)
      }
      err = fmt.Errorf(errorMsg)
    }

    return
  })

  return &tool{
    action: toolAction,
  }, nil
}

// LookupTool looks up the tool in the registry by provided name and returns it.
func LookupTool(serverName, name string) ai.Tool {
  return &tool{action: registry.Global.LookupAction(fmt.Sprintf("/tool/%s/%s/%s", provider, serverName, name))}
}

func LookupTools(serverName string) (tools []ai.Tool) {
  for _, desc := range registry.Global.ListActions() {
    if strings.HasPrefix(desc.Key, fmt.Sprintf("/tool/%s/%s/", provider, serverName)) {
      tools = append(tools, &tool{
        action: registry.Global.LookupAction(desc.Key),
      })
    }
  }

  return
}
