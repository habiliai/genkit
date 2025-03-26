package mcp_test

import (
  "context"
  "encoding/json"
  "github.com/firebase/genkit/go/plugins/mcp"
  "testing"

  mcpclient "github.com/mark3labs/mcp-go/client"
  mcpgo "github.com/mark3labs/mcp-go/mcp"
)

func TestMCPToolCall(t *testing.T) {
  ctx := context.TODO()

  c, err := mcpclient.NewStdioMCPClient("npx", []string{}, "-y", "@modelcontextprotocol/server-filesystem", ".")
  if err != nil {
    t.Fatalf("failed to create MCP client: %v", err)
  }
  defer c.Close()

  initRequest := mcpgo.InitializeRequest{}
  initRequest.Params.ProtocolVersion = mcpgo.LATEST_PROTOCOL_VERSION
  initRequest.Params.ClientInfo = mcpgo.Implementation{
    Name:    "example-client",
    Version: "1.0.0",
  }
  if _, err := c.Initialize(ctx, initRequest); err != nil {
    t.Fatalf("failed to initialize MCP client: %v", err)
  }

  listToolsRes, err := c.ListTools(ctx, mcpgo.ListToolsRequest{})
  if err != nil {
    t.Fatalf("failed to list tools: %v", err)
  }
  var listDirTool mcpgo.Tool
  for _, tool := range listToolsRes.Tools {
    if tool.Name == "list_directory" {
      listDirTool = tool
      break
    }
  }
  tool, err := mcp.DefineTool(c, "filesystem", listDirTool)
  if err != nil {
    t.Fatalf("failed to define tool: %v", err)
  }

  t.Run("Run Tool", func(t *testing.T) {
    result, err := tool.Action().RunJSON(ctx, []byte(`{"path":"./"}`), nil)
    if err != nil {
      t.Fatalf("failed to run tool: %v", err)
    }

    var output mcp.Content
    if err := json.Unmarshal(result, &output); err != nil {
      t.Fatalf("failed to unmarshal result: %v", err)
    }

    t.Logf("result: %+v", output)
  })

  t.Run("Lookup tools", func(t *testing.T) {

    tools := mcp.LookupTools("filesystem")
    if len(tools) == 0 {
      t.Fatalf("no tools found")
    }

    if tools[0].Definition().Name != tool.Definition().Name {
      t.Fatalf("expected tool name to be list_directory, got %s", tools[0].Definition().Name)
    }
    if tools[0].Definition().Description != tool.Definition().Description {
      t.Fatalf("expected tool description to be List the contents of a directory, got %s", tools[0].Definition().Description)
    }
  })
}
