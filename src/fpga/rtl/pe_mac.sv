module pe_mac(input wire clk,rst, input wire init, input wire signed [31:0] bias,
 input wire step, input wire signed [7:0] qx,zx,qw,
 input wire finish, output wire ready, output reg valid,
 input wire out_ready, output reg signed [31:0] acc, output reg overflow);
 wire signed [8:0] centered=$signed({qx[7],qx})-$signed({zx[7],zx});
 wire signed [16:0] product=centered*qw;
 wire signed [32:0] sum=$signed({acc[31],acc})+$signed({{16{product[16]}},product});
 assign ready=!valid && !overflow;
 always @(posedge clk) begin
  if(rst) begin acc<=0;valid<=0;overflow<=0;end
  else begin
   if(valid&&out_ready)valid<=0;
   if(init&&ready)acc<=bias;
   if(step&&ready) begin
    if(qw==-128 || sum[32]!=sum[31])overflow<=1;
    else acc<=sum[31:0];
   end
   if(finish&&ready)valid<=1;
  end
 end
endmodule
