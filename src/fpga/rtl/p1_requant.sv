// Person1 draft: full precision signed RNE, no ReLU. Combinational numerical core.
module p1_requant(input wire signed [31:0] acc,m,
 input wire [31:0] shift,input wire signed [7:0] zy,
 output wire signed [63:0] product,rounded,output wire signed [64:0] raw,
 output wire signed [7:0] value,output wire illegal);
 assign illegal=m<=0 || shift>62;
 assign product=acc*m;
 wire [63:0] mask=(64'd1<<shift)-1;
 wire [63:0] remnant=$unsigned(product)&mask;
 wire [63:0] half=64'd1<<(shift-1);
 wire signed [63:0] quotient=product>>>shift;
 wire up=(shift!=0)&&((remnant>half)||((remnant==half)&&quotient[0]));
 assign rounded=quotient+$signed({63'd0,up});
 assign raw=$signed({rounded[63],rounded})+$signed({{57{zy[7]}},zy});
 assign value=raw>127 ? 8'sd127 : raw< -128 ? -8'sd128 : raw[7:0];
endmodule
